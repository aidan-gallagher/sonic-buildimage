#!/usr/bin/python3

import subprocess
import json
import pwd


def get_users_from_db():
    result = subprocess.run(
        ["sonic-cfggen", "-d", "--var-json", "LOCAL_LOGIN"],
        text=True,
        capture_output=True,
    ).stdout
    db_users = json.loads(result) if result else {}
    return db_users


def get_users_from_linux():
    # Find all non-service accounts (id > 1000) and delete them if they are not in CONFIG_DB.
    linux_users = []
    for p in pwd.getpwall():
        if p.pw_uid >= 1000 and p.pw_uid < 60000:  # Regular user UIDs start from 1000
            linux_users.append(p.pw_name)
    return linux_users


def apply_db_state_to_linux(db_users, linux_users):

    # If there are no db_users then this feature isn't enabled - exit without making any changes.
    if not db_users:
        return 0

    for db_user in db_users:
        password = db_users[db_user].get("password")
        if password == None:
            print(
                f"Error: Local login: Configured user {db_user} doesn't have a password set"
            )
            continue

        # Create user if they don't exist yet.
        if db_user not in linux_users:
            subprocess.run(
                ["sudo", "useradd", "--create-home", "--shell", "/bin/bash", db_user],
                text=True,
                capture_output=True,
            )

        # Make user a sudo-er.
        subprocess.run(
            ["sudo", "usermod", "-aG", "sudo", db_user], text=True, capture_output=True
        )

        # Set user's password.
        credentials_input = f"{db_user}:{password}"
        subprocess.run(
            ["sudo", "chpasswd", "-e"],
            text=True,
            input=credentials_input,
            capture_output=False,
        )

    for linux_user in linux_users:
        if linux_user not in db_users:
            # Force delete the user in case they are logged in. The CLI command will do the warning that the user is logged in
            # Remove home directory so if operator creates a new user with the same name there won't be problems.
            subprocess.run(["sudo", "userdel", "--force", linux_user], check=True)
            subprocess.run(["sudo", "rm", "-rf", f"/home/{linux_user}"], check=True)


if __name__ == "__main__":
    db_users = get_users_from_db()
    linux_users = get_users_from_linux()
    apply_db_state_to_linux(db_users, linux_users)
