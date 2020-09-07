# introduction
specter-desktop is using gitlab and Travis-CI for continuous integration purposes. Both have advantages and disadvantages so ... let's use both!
Gitlab:
* is completely open Source for server- and clients
* the gitlab-runner can run docker and is itself running on docker
* but does not support Pull-Requests
* needs to have bitcoind in a prepared docker-container which binds the build to that version

Travis-CI:
* supports the PR-model
* quite easy to setup even without docker
* enables to test against any specific version of bitcoind we would like to

# Gitlab

Gitlab is a great CI/CD-platform and in the meantime it's quite easy to use it for github-repositories.
https://docs.gitlab.com/ee/ci/ci_cd_for_external_repos/github_integration.html
The main file which specifies the jobs on gitlab is .gitlab-ci.yml
We're using a gitlab-docker-runner which means that all jobs are running in a container.
However at the same time we're using docker to spinup a bitcoind. 

The image is created manually (see /docker) and used for running the tests AND also for 
spinning up bitcoind.

For that reason we need to share the docker-socket from the host into the container and 
create our own gitlab specific runner as described here: 
https://docs.gitlab.com/ee/ci/docker/using_docker_build.html#use-docker-socket-binding

Due to that setup there are some specifics which are mainly addressed in tests/conftest 
start_bitcoind-function:
* some pytest specific stuff to enable "pytest --docker" (used in .gitlab-ci.yml)
* adding -rpcallowip= (from a docker network) to bitcoind
* not use localhost but the docker-network-ip-address when talking to the bitcoind

# Travis-CI

Travis-CI setup is very straightforward. As we're using the build-cache, the bitcoind sources and build is cached. Therefore such a build would only take 2 minutes. If the master-branch has new commits, bitcoind gets automatically rebuilt and the tests are running against the new version (tests/install_bitcoind.sh).py

# Releasing

## pip-based release to pypi

We're about to release (semi-) automatically. The relevant release-artifact is a pip-package which will get released to pypi.org. A manual description of how to create this kind of releases can be found [here](https://packaging.python.org/tutorials/packaging-projects/). 
In a nutshell and also for testing purposes:
```
# Modify the version in setup.py
# create package:
python3 setup.py sdist bdist_wheel
# install dependencies for uploading
python3 -m pip install --upgrade twine
# uploading
python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
# enter username and password (maybe register at https://test.pypi.org)
# Let's test the package in a new virtualenv:
cd /tmp && mkdir specter-release-test && cd specter-release-test
virtualenv --python=python3 .env
source .env/bin/activate
# Workaround because dependencies are not availabe on test.pypi.org
wget https://raw.githubusercontent.com/cryptoadvance/specter-desktop/master/requirements.txt
python3 -m pip install -r requirements.txt  
# Install the package
python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps cryptoadvance.specter
# AND Ready to go! e.g.:
python3 -m cryptoadvance.specter server

```


The automation of that kicks in if someone creates a tag which is named like "vX.Y.Z". This is specified in the gitlab-ci.yml. The release-job will only be triggered in cases of tags. One step will also check that the tag follows the convention above.
The package upload will need a token. How to obtain the token is described in the packaging-tutorial. It's injected via gitlab-variables. ToDo: put the token on a trusted build-node.

The alternative would have been to use travis-ci for releasing. In that case we would encrypt the token with a private-key from travis and commit to the repo. This looks more safe to me then the above scenario but less safe then the todo, where we're storing the token on the build-node.

## pyinstaller system-dependent binaries
The [pyinstaller directory](../pyinstaller) contains scripts to create the platform-specific binaries to use specter-desktop as a desktop-software. Some of them are created and uploaded to [github-releases](https://github.com/cryptoadvance/specter-desktop/releases) via more or less special build-agents.
The [windows-build-agent](https://docs.gitlab.com/runner/install/windows.html) needs manual installation 
of git, python and docker. Docker is used to build the innosetup-file.
As docker is available in windows only as a "desktop-edition", one need to also
log into the windows-machine to get docker started.
Clearly there is an opportunity to move all of the creation of the windows-binary to wine on docker,
similiar to the way the innosetup is running withon docker.

#  Summary

It's great to use both systems but it would be better to have the fixed version (as in the dockerimages of gitlab) in the PRs and the updated tests against the newest version (as in install_bitcoind.sh used by travis-CI) for daily/monthly builds. 
Anyway, good enough for now. 
