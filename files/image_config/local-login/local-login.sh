#!/bin/bash -e

ENABLED=$(sonic-cfggen -d -v "LOCAL_LOGIN")
if [ -z "${ENABLED}" ]; then
	echo Local password not set - leaving
	exit 0
fi

PASSWORD=$(sonic-cfggen -d -v "LOCAL_LOGIN['global']['password']")
echo "admin:${PASSWORD}" | sudo chpasswd -e

# TODO: Remove the commented out line below once I'm happy chpasswd -e is working
#sudo sed -i s#^admin:[^:]*:#admin:${PASSWORD}:#g /etc/shadow 

