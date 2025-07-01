#!/usr/bin/python3

import subprocess
import json
import pwd
import os
import shutil
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
    if 'remote_user_su' in user_info.pw_gecos or 'remote_user' in user_info.pw_gecos:
        return True
    return False


def apply_sonic_config_to_linux(ssh_keys, local_login_users, linux_users):

    # If ssh-login and local-login isn't configured then exit without making changes. This preserves backwards compatibilty
    # which allows operators to continue using native Linux commands (i.e. adduser) if they prefer.
    if not ssh_keys and not local_login_users:
        return
    
    ssh_users = set()

    # ------------------------------ Authorized keys ----------------------------- #
    # Remove all authorized_keys.
    auth_keys_dir = "/etc/ssh/authorized_keys"
    logging.info(f"Deleting f{auth_keys_dir} to remove all system wide keys.")
    if os.path.exists(auth_keys_dir):
        shutil.rmtree(auth_keys_dir)

    # For each key, find the user and append their key to the file /etc/ssh/authorized_keys/{user}.
    # Populate ssh_users.
    for db_key in ssh_keys:
        ssh_user = db_key.split("|")[0]
        ssh_users.add(ssh_user)
        ssh_public_key = ssh_keys[db_key]["ssh-public-key"]
        logging.info(
            f"Configuring user {ssh_user} with ssh-public-key \"{ssh_public_key}\"."
        )

        os.makedirs(auth_keys_dir, mode=0o755, exist_ok=True)
        auth_keys_file = os.path.join(auth_keys_dir, ssh_user)
        with open(auth_keys_file, "a") as f:
            f.write(ssh_public_key + "\n")

    # ------------------------------ Add Linux Users ----------------------------- #
    # Ensure each user configured with ssh login has a valid Linux account.
    for ssh_user in ssh_users:
        if ssh_user not in linux_users:
            logging.info(f"{ssh_user} does not exist yet so creating user.")
            subprocess.run(
                ["sudo", "useradd", "--create-home", "--shell", "/bin/bash", ssh_user],
                text=True,
                capture_output=True,
            )
            subprocess.run(
                ["sudo", "usermod", "-aG", "sudo,redis,docker", ssh_user],
                text=True,
                capture_output=True,
            )

    # ---------------------------- Delete Linux Users ---------------------------- #
    # Delete any Linux users (excluding remote users) that aren't configured by local-login or ssh-login.
    # Force delete the user in case they are logged in.
    for linux_user in linux_users:

        # Skip remote users (tacas, radius) because we don't want to delete these users.
        if is_remote_user(linux_user):
            continue

        if linux_user not in ssh_users and linux_user not in local_login_users:
            logging.info(
                f"Linux user {linux_user} is not configured with local-login or ssh-login so remove the user and their home directory."
            )
            subprocess.run(["sudo", "userdel", "--force", linux_user], check=True)
            subprocess.run(["sudo", "rm", "-rf", f"/home/{linux_user}"], check=True)


if __name__ == "__main__":
    logging.info("ssh-login started")
    ssh_keys = get_ssh_keys()
    local_login_users = get_local_login_users()
    linux_users = get_users_from_linux()
    apply_sonic_config_to_linux(ssh_keys, local_login_users, linux_users)
    logging.info("ssh-login finished")
