#!/bin/bash

# This script prepares the shell so that it can do git-pushes
# It's using the first param as the secret key and the env-var
# KNOWN_HOSTS.


## Install ssh-agent if not already installed, it is required by Docker.
## (change apt-get to yum if you use an RPM-based image)
##
which ssh-agent || ( apk update && apk add --no-cache bash git openssh )
docker info

##
## Run ssh-agent (inside the build environment)
##
eval $(ssh-agent -s)

##
## Add the SSH key stored in SSH_PRIVATE_KEY variable to the agent store
## We're using tr to fix line endings which makes ed25519 keys work
## without extra base64 encoding.
## https://gitlab.com/gitlab-examples/ssh-private-key/issues/1#note_48526556
##
echo "$1" | tr -d '\r' | ssh-add - > /dev/null

##
## Create the SSH directory and give it the right permissions
##
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Check if Git user email is not set
if [ -z "$(git config --global --get user.email)" ]; then
    git config --global user.email "specter@secretvalues"
fi

# Check if Git user name is not set
if [ -z "$(git config --global --get user.name)" ]; then
    git config --global user.name "specter"
fi

# Check if KNOWN_HOSTS is set and not empty
if [ -n "$KNOWN_HOSTS" ]; then
  # Add KNOWN_HOSTS to known_hosts file
  echo "$KNOWN_HOSTS" > ~/.ssh/known_hosts
  # Ensure the file permissions are correct
  chmod 644 ~/.ssh/known_hosts
fi
