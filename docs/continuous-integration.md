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

We're not yet ready to release (semi-) automatically. The current release-artifact is based on pyinstaller. To create the pyinstaller-artifact:
```
$ pyinstaller --onefile  --clean --paths .env/lib/python3.7/site-packages:src/specter  --add-data 'src/specter/templates:templates' --add-binary '.env/bin/hwi:.'  --add-data 'src/specter/static:static' src/specter/server.py
```
It would be great to name the app like --name specter-desktop  but the binary created is crashing the app after successfull startup for some unknown reason.

#  Summary

It's great to use both systems but it would be better to have the fixed version (as in the dockerimages of gitlab) in the PRs and the updated tests against the newest version (as in install_bitcoind.sh used by travis-CI) for daily/monthly builds. 
Anyway, good enough for now. 
