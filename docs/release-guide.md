# Release Guide

## Creating release notes

### Pre-requisites

- You need the correct upstream master. You should see

```bash
git remote -v | grep upstream
upstream        git@github.com:cryptoadvance/specter-desktop.git (fetch)
upstream        git@github.com:cryptoadvance/specter-desktop.git (push)
```

- You need a GitHub token:
  If you don't have one, get one here https://github.com/settings/tokens and make sure to tick the boxes for repo and workflow as below:

![](./images/release-guide/github-token.png)

Using the new token, run

```bash
export GH_TOKEN=YOURTOKEN
```

- You need Docker running
- Checkout the master branch and ensure a clean workspace.

Now, you can run

```bash
./utils/release.sh --release-notes
```

Or, if you want to directly set the new version:

```bash
./utils/release.sh --new-version v1.13.1 --release-notes
```

## Creating a new tag

Update your master branch after the release notes PR ([example](https://github.com/cryptoadvance/specter-desktop/commit/65ff6959d7fd85cba745e4d454b30031839f857f/)) has been merged and then run:

```bash
git tag v1.13.1 && git push upstream v1.13.1
```

## GitLab - releasing stage

Creating a tag triggers the release process of the GitLab runners.
There exists a mirror of the GitHub repo on GitLab, but only when a tag is created on GitHub will the release part of the runners execute. You can check the status here:
https://gitlab.com/cryptoadvance/specter-desktop/-/pipelines

There are three stages:
![](./images/release-guide/overview-gitlab-pipline.png)

The first relevant stage is "releasing". Here, the Windows, Linux and pip release are created and uploaded to the Specter Desktop GitHub releases page. After this stage, the following artificats should be available:

- cryptoadvance.specter-1.13.1.tar.gz
- Specter-Setup-v1.13.1.exe
- specterd-v1.13.1-win64.zip
- specterd-v1.13.1-x86_64-linux-gnu.zip
- specter_desktop-v1.13.1-x86_64-linux-gnu.tar.gz

The three jobs in more detail:

- release_binary_windows: is creating a binary for specterd and for Windows (Windows runner)
- release_electron_linux_windows: Creates a specterd for Linux, an AppImage for Linux and an executable for Windows (Linux runner).
- release_pip: Is releasing a pypi package on [pypi](https://pypi.org/project/cryptoadvance.specter/) and creates a tarball of the pip package for the GitHub release page (Linux runner).

For details look at `.gitlab-ci.yml`

## MacOS

Ideally, directly after the tag is created, start with the MacOS release. This has to be done manually, for now. There is a script for this:

```bash
./utils/build-osx.sh  --version v1.13.1 --appleid "Satoshi Nakamoto (appleid)" --mail "satoshi@gmx.com" make-hash specterd electron sign upload
```

This script also runs `github.py upload `, so two more binares and the hash and signature files are uploaded to GitHub:

- Specter-v1.13.1.dmg
- specterd-v1.13.1-osx.zip
- SHA256SUMS-macos
- SHA256SUMS-macos.asc

## GitLab - post releasing

Back to GitLab, the final stage is "post releasing".

In this stage, the invididual SHA256-hashes and signatures are combined into two final files:

- SHA256SUMS
- SHA256SUMS.asc

Everything, apart from the MacOS files, are pulled from the GitLab environment, the MacOS files from GitHub.
Don't forget to delete the two MacOS files (`SHA256SUMS-macos` and `SHA256SUMS-macos.asc`) on the GitHub release page in the end.

## Trouble shooting

If the MacOS signatures are missing, it can happen that the following Exception will be raised:

```bash
  File "/builds/cryptoadvance/specter-desktop/utils/github.py", line 295, in download_artifact
  raise Exception(
  Exception: Status-cod04 for url ... )
```

In any case, if the macOS binaries arrive on GitHub too late, you have to manually delete the already created `SHA256SUMS` and `SHA256SUMS.asc`, otherwise the upload to GitHub will fail if you rerun the release signatures job on GitLab - for details see ([this PR](https://github.com/cryptoadvance/specter-desktop/pull/689)). The green arrow in the screenshot is where you rerun the release signatures job on GitLab:

![](./images/release-guide/rerun-release-signatures.png)

## GitHub release page and download page

This is handled by the script `./utils/generate_downloadpage.sh`. As a prerequisite, you need to clone the `specter-static` repo which contains the specter website. Clone it on the same level than specter-desktop.
Running that script will:

- install the prerequisites (basically markdown, see pyproject.toml)
- generate the GH-page and the download-page based on the `utils/templates`.
- Asks whether it should replace/update/initialize the Github Release page for the latest version
- copies over the new download-pages and asks whether it should commit/push those
