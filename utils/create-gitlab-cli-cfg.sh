#!/bin/bash

cat > ~/.python-gitlab.cfg << EOF
[global]
default = specterdesktop
ssl_verify = true
timeout = 5

[specterdesktop]
url = https://gitlab.com
#private_token = ${CI_JOB_TOKEN}
job_token =${CI_JOB_TOKEN}
api_version = 4


EOF
