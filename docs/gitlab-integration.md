# introduction
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



