#!/bin/bash

payload="{\"ref\":\"master\", \"inputs\": {\"tag\": \"${CI_COMMIT_TAG}\"}}"
echo $payload
# This Token is controlled by https://github.com/AaronDewes

curl -X POST -H "Accept: application/vnd.github.v3+json" -H "Authorization: token ${AARON_TOKEN}" \
    https://api.github.com/repos/lncm/docker-specter-desktop/actions/workflows/dispatch.yml/dispatches  -d @<(cat <<EOF
$payload
EOF
)