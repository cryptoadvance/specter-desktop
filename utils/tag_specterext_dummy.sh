#!/bin/bash
set -e

echo "This script will checkout github.com:${CI_PROJECT_ROOT_NAMESPACE}/specterext-dummy.git"
echo "and tag it with ${CI_COMMIT_TAG}"


git clone git@github.com:${CI_PROJECT_ROOT_NAMESPACE}/specterext-dummy.git

cd specterext-dummy
git checkout master
git tag ${CI_COMMIT_TAG}
git push origin ${CI_COMMIT_TAG}
