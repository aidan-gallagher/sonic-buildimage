#!/usr/bin/python3

import subprocess
import json
import pwd
import logging
import sys


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def get_ssh_keys():
    result = subprocess.run(
        ["sonic-cfggen", "-d", "--var-json", "SSH_LOGIN"],
        text=True,
        capture_output=True,
    ).stdout
    ssh_keys = json.loads(result) if result else {}
    return ssh_keys


def get_local_login_users():
    result = subprocess.run(
        ["sonic-cfggen", "-d", "--var-json", "LOCAL_LOGIN"],
        text=True,
        capture_output=True,
    ).stdout
    local_login_users = json.loads(result) if result else {}
    return local_login_users


def get_users_from_linux():
    # Find all non-service accounts.
    linux_users = []
    for p in pwd.getpwall():
        if p.pw_uid >= 1000 and p.pw_uid < 60000:
            linux_users.append(p.pw_name)
    return linux_users


def is_remote_user(username):
    # All Radius and Tacas users have either remote_user or remote_user_su in their gecos field
    # TODO: Does LDAP have this?
    user_info = pwd.getpwnam(username)
    if "remote_user_su" in user_info.pw_gecos or "remote_user" in user_info.pw_gecos:
        return True
    return False


def apply_sonic_config_to_linux(ssh_keys, local_login_users, linux_users):

    # If ssh-login and local-login isn't configured then exit without making changes. This preserves backwards compatibilty
    # which allows operators to continue using native Linux commands (i.e. adduser) if they prefer.
    if not ssh_keys and not local_login_users:
        return

    for db_user in local_login_users:
        logging.info(f"Configuring user {db_user}")

        password = local_login_users[db_user].get("password")
        if password == None:
            logging.error(
                f"Error: Configured user {db_user} doesn't have a password set. Skipping configuration of this user."
            )
            continue

        # -------------------------------- Create User ------------------------------- #
        # Create user if they don't exist yet.
        if db_user not in linux_users:
            logging.info(f"{db_user} does not exist yet so creating user.")
            subprocess.run(
                ["sudo", "useradd", "--create-home", "--shell", "/bin/bash", db_user],
                text=True,
                capture_output=True,
            )

        # Ensure user is in correct groups
        subprocess.run(
            ["sudo", "usermod", "-aG", "sudo,redis,docker", db_user],
            text=True,
            capture_output=True,
        )

        # ------------------------------- Set Password ------------------------------- #
        credentials_input = f"{db_user}:{password}"
        logging.info(f"Setting {db_user}'s password.")
        subprocess.run(
            ["sudo", "chpasswd", "-e"],
            text=True,
            input=credentials_input,
            capture_output=False,
        )

    # ------------------------------- Get ssh users ------------------------------ #
    ssh_users = set()
    for db_key in ssh_keys:
        ssh_user = db_key.split("|")[0]
        ssh_users.add(ssh_user)

    # ---------------------------- Delete Linux Users ---------------------------- #
    # For each Linux user (excluding remote users) if they aren't configured with local-login then remove their password.
    # If they aren't configured with local-login and ssh-login then remove the user.
    # Force delete the user in case they are logged in.
    for linux_user in linux_users:

        # Skip remote users (tacas, radius) because we don't want to delete these users.
        if is_remote_user(linux_user):
            continue

        if linux_user not in local_login_users:
            logging.info(
                f"Linux user {linux_user} is not configured with local-login so remove their password"
            )
            subprocess.run(["sudo", "passwd", "-d", linux_user], check=True)

            if linux_user not in ssh_users:
                logging.info(
                    f"Linux user {linux_user} is not configured with local-login or ssh-login so remove the user and their home directory."
                )
                subprocess.run(["sudo", "userdel", "--force", linux_user], check=True)
                subprocess.run(["sudo", "rm", "-rf", f"/home/{linux_user}"], check=True)


if __name__ == "__main__":
    logging.info("local-login started")
    ssh_keys = get_ssh_keys()
    local_login_users = get_local_login_users()
    linux_users = get_users_from_linux()
    apply_sonic_config_to_linux(ssh_keys, local_login_users, linux_users)
    logging.info("local-login finished")
