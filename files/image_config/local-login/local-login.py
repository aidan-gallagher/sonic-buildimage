#!/usr/bin/python3

import subprocess
import json
import pwd

# sonic-cfggen -d --var-json 'LOCAL_LOGIN'

result = subprocess.run(['sonic-cfggen', '-d', '--var-json', 'LOCAL_LOGIN'], text=True, capture_output=True).stdout
print(result)
result_dict = json.loads(result)

for user in result_dict:
	password = result_dict[user]["password"]

	print(user, password)
	# Create user if they don't exist yet
	success = subprocess.run(['id', user], text=True, capture_output=True).returncode
	if success == 0:
		pass
	else:
		print("creating user")
		subprocess.run(['sudo', 'useradd', '--create-home', '--shell', '/bin/bash', user], text=True, capture_output=True)

	subprocess.run(['sudo', 'usermod', '-aG', 'sudo', user], text=True, capture_output=True)

	# Set users password
	credentials_input = f"{user}:{password}"
	subprocess.run(['sudo', 'chpasswd', '-e'], text=True, input=credentials_input, capture_output=False)

# Find all non-service accounts (id > 1000) and delete them if they are not in CONFIG_DB
users = []
for p in pwd.getpwall():
	if p.pw_uid >= 1000 and p.pw_uid < 60000:  # Regular user UIDs start from 1000
		users.append(p.pw_name)

for user in users:
	if user not in result_dict:
		# Force delete the user in case they are logged in. The CLI command will do the warning that the user is logged in
		# Remove home directory so if operator creates a new user with the same name there won't be problems.
		subprocess.run(['sudo', 'userdel', '--force', user], check=True)
		subprocess.run(['sudo', 'rm', '-rf', f'/home/{user}'], check=True)