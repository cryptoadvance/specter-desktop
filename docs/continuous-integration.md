# Introduction
Specter-Desktop is using GitLab, Cirrus and GitHub-Actions for continuous integration purposes but GitHub-actions only for Blackify so far. It might be more effort using more than one CI-approach but it makes us also more resilient. 
GitLab and Cirrus have both advantages and disadvantages so ... let's use both!
GitLab:
* is completely open Source for server- and clients
* the gitlab-runner can run docker and is itself running on docker
* but does not support Pull-Requests
* needs to have bitcoind in a prepared docker-container which binds the build to that version

Cirrus-CI:
* supports the PR-model
* quite easy to setup even though it's using docker

## Gitlab

Gitlab is a great CI/CD-platform and in the meantime it's quite easy to use it for GitHub-repositories.
https://docs.gitlab.com/ee/ci/ci_cd_for_external_repos/github_integration.html
The main file which specifies the jobs on GitLab is .gitlab-ci.yml
We're using a `gitlab-docker-runner` which means that all jobs are running in a container.
However at the same time we're using docker to spinup a bitcoind. 

The image is created manually (see /docker) and used for running the tests AND also for 
spinning up bitcoind.

For that reason we need to share the docker-socket from the host into the container and 
create our own GitLab specific runner as described here: 
https://docs.gitlab.com/ee/ci/docker/using_docker_build.html#use-docker-socket-binding

Due to that setup there are some specifics which are mainly addressed in tests/conftest 
start_bitcoind-function:
* adding -rpcallowip= (from a docker network) to bitcoind
* not use localhost but the docker-network-ip-address when talking to the bitcoind

## Travis-CI

We're no longer using travis-ci due to the abuse-detection-system going wild on us.

## Cirrus-CI

[Cirrus-CI](https://cirrus-ci.org) is used by Bitcoin-Core and HWI and is a quite good replacement for travis. We're using it only for PRs so far. The [../.cirrus.yml] file defines the build. We have two task, one for pytest and one for the [cypress-tests](./cypress-testing.md).

## Releasing

### What gets released

We're mostly releasing automatically. Currently the following artifacts are released:
* specterd (daemon) is a binary for kicking off the specter-desktop service on the command-line. We have binaries for windows, Linux and macOS
* We have an Electron-App which we're also releasing for Windows, Linux and MacOS. Unfortunately the macOS build is not yet automated
* We release a pip-package
* Usually some time after the release, the lncm is releasing [docker-images](https://hub.docker.com/r/lncm/specter-desktop). Very much appreciated, even though we can't guarantee for them, obviously.

### How we release
As we have a strict build-only-on-private-hardware build-policy, we're using GitLab private runners in order to build our releases. In order to test and develop the releasing automation, people can setup GitLab-projects which are syncing from their GitHub-forks. With such a setup it's possible to create test-releases and therefore test the whole procedure end-to-end.

The automation of that kicks in if someone creates a tag which is named like "vX.Y.Z". This is specified in the gitlab-ci.yml. The release-job will only be triggered in cases of tags. One step will also check that the tag follows the convention above.
The package upload will need a token. How to obtain the token is described in the packaging-tutorial. It's injected via GitLab-variables. ToDo: put the token on a trusted build-node.

### pyinstaller system-dependent binaries
The [pyinstaller directory](../pyinstaller) contains scripts to create the platform-specific binaries (plus electron) to use specter-desktop as a desktop-software. Some of them are created and uploaded to [GitHub-releases](https://github.com/cryptoadvance/specter-desktop/releases) via more or less special build-agents.
The [windows-build-agent](https://docs.gitlab.com/runner/install/windows.html) needs manual installation 
of git, python and docker. Docker is used to build the innosetup-file.
As docker is available in windows only as a "desktop-edition", one need to also
log into the windows-machine to get docker started.
Clearly there is an opportunity to move all of the creation of the windows-binary to wine on docker,
similiar to the way the innosetup is running within docker.

## CI/CD-dev-env setup

Here is a brief description on how to create a setup where the release-procedures can be tested:
* We assume you have a fork of cryptoadvance/specter-desktop. We also assume that your GitLab-user-handle is the exact same as on GitHub.
* Create a GitLab-account and then a mirroring project ([here](https://gitlab.com/projects/new#cicd_for_external_repo)) obviously with the exact same name: "specter-desktop"
* Activate the private runners and deactivate the public runners. Contact @k9ert for that.
* Create an account and an [API token](https://test.pypi.org/manage/account/) on there
* Create a token for GitHub in order to release to your GitHub-fork
* Configure both tokens on the GitLab-variables (GH_BIN_UPLOAD_PW and TWINE_PASSWORD)
* create a tag on your GitHub-fork
* watch the test-release unfolding, ready to hack

### GitLab-runner setup (Windows)

For Windows-releasing, we're using a windows GitLab-runner. Here is a short description on how to set one up.

#### Prerequisites

You need at least Windows Home 10 which is up-to-date. The most complex dependency is setting up docker.
Docker-Desktop needs a WSL2 which is a good idea to install on windows anyway. [Here](https://www.omgubuntu.co.uk/how-to-install-wsl2-on-windows-10) is a description on how to do that.

While installing, make sure you know the locations of where that stuff is installed. We'll later need to verify/adjust the PATH.

* Install Python, i took the [3.7.9 webinstaller](https://www.python.org/ftp/python/3.7.9/python-3.7.9-amd64-webinstall.exe)
* Install Git, e.g. [this](https://github.com/git-for-windows/git/releases/download/v2.29.2.windows.2/Git-2.29.2.2-64-bit.exe) (i had 2.28.2)
* Install [Docker-Desktop](https://desktop.docker.com/win/stable/Docker%20Desktop%20Installer.exe)

Now open and check the "Environment-variables" and check that the following lines are in there:

![](./images/continuous-integration_runner_windows_envvars.png)

#### Runner

The runner itself is easy to [setup](https://docs.gitlab.com/runner/install/windows.html). Follow the link or this very brief description:
*  `mkdir \Gitlab-Runner`
* download [this binary](https://gitlab-runner-downloads.s3.amazonaws.com/latest/binaries/gitlab-runner-windows-amd64.exe) in that folder and rename to gitlab-runner.exe
* Search for "powershell" in windows an open AS ADMINISTRATOR
* `cd \Gitlab-Runner`
* Copy the Registration-token from [here](https://gitlab.com/k9ert/specter-desktop/-/settings/ci_cd) (unfold runners, see specific runners)
* `./gitlab-runner.exe register`and paste the token (the instance-url is the default)
* give a reasonable description. Make sure to tag this runner with "tag". If that's not possible here, you can do it in the page mentioned above
* `.\gitlab-runner.exe install` will install the runner as system-service
* `.\gitlab-runner.exe start` will start it

Done
