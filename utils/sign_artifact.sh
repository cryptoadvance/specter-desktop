#!/bin/bash

while [[ $# -gt 0 ]]
do
key="$1"
command="main"
case $key in
    --artifact)
    artifact=$2
    shift
    shift
    ;;
    --debug)
    set -x
    shift # past argument
    ;;
    *)    # unknown option
    POSITIONAL="$1" # save it in an array for later
    shift # past argument
    ;;
esac
done

if [[ -z $artifact ]]; then
    echo "no --artifact given "
    exit 1
fi


# We want a detached signature in cleartext. Extension: .asc (as in bitcoin)
output_file=${artifact}.asc

if [[ -f /credentials/private.key ]]; then 
    echo "Importing single private key"
    gpg --import --no-tty --batch --yes /credentials/private.key
fi

if [[ -f /credentials/gnupg.tar.gz ]]; then 
    echo "extracting gnupg.tar.gz"
    tar -xzf /credentials/gnupg.tar.gz -C /root
    chown -R root:root ~/.gnupg
fi

echo "signing ..."
echo $GPG_PASSPHRASE | gpg --detach-sign --armor --no-tty --batch --yes --passphrase-fd 0  --pinentry-mode loopback $artifact 
