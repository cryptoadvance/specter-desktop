#!/bin/bash

function sub_help {
    echo "This script is to sign artifacts or to prepare the gpg-system to be able to verify artifacts."
    echo "Do one of these:"
    echo "$  ./utils/artifact_signer.sh init"
    echo "This makes sense only on a gitlab-runner. It'll unpack a gpg-directory to be ready to sign and verify"
    echo "$ ./utils/artifact_signer.sh sign --artifact ./release-win/SHA256SUMS-win"
    echo "Signs a specific artifact. Will do the init on the fly. So no need to call it extra."
}

while [[ $# -gt 0 ]]
do
key="$1"
command="main"
case $key in
    --help)
    sub_help
    exit
    shift
    ;;
    --artifact)
    artifact=$2
    shift
    shift
    ;;
    sign)
    action=sign
    shift
    ;;
    init)
    action=init
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

# We want a detached signature in cleartext. Extension: .asc (as in bitcoin)
output_file=${artifact}.asc

# lazy init: We're initializing Each thime script is called with these two things.
# So that action "init" is just to have a bit more semantics for the one calling this script

function init {
    if [[ -f /credentials/gnupg.tar.gz ]]; then 
        echo "Init: extracting gnupg.tar.gz"
        tar -xzf /credentials/gnupg.tar.gz -C /root
        chown -R root:root ~/.gnupg
    else
        echo "Init: Could not find any /credentials/gnupg.tar.gz"
    fi

    if [[ -f /credentials/private.key ]]; then 
        echo "Init: Importing single private key"
        gpg --import --no-tty --batch --yes /credentials/private.key
    else
        echo "Init: Could not find any /credentials/private.key"
    fi
}

if [ "$action" = "init" ]; then
    init
fi

if [ "$action" = "sign" ]; then
    init
    if [[ -z $artifact ]]; then
        echo "no --artifact given "
        exit 1
    fi
    echo "signing ..."
    echo $GPG_PASSPHRASE | gpg --detach-sign --armor --no-tty --batch --yes --passphrase-fd 0  --pinentry-mode loopback $artifact 
fi