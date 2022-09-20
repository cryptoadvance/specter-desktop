Used for building the electron-app. In short it's the /pyinstaller/build-unix.sh script which is running in this image.

By intention, this is using an older OS-version in order to avoid glibc-issues. For details, see:
* https://github.com/cryptoadvance/specter-desktop/pull/1688#issuecomment-1242796681
* https://github.com/cryptoadvance/specter-desktop/issues/373#issuecomment-695068924


If you want to run the image manually, do something like this (copied from [here](https://www.electron.build/multi-platform-build#build-electron-app-using-docker-on-a-local-machine)):


```
docker run --rm -ti \
 --env-file <(env | grep -iE 'DEBUG|NODE_|ELECTRON_|YARN_|NPM_|CI|CIRCLE|TRAVIS_TAG|TRAVIS|TRAVIS_REPO_|TRAVIS_BUILD_|TRAVIS_BRANCH|TRAVIS_PULL_REQUEST_|APPVEYOR_|CSC_|GH_|GITHUB_|BT_|AWS_|STRIP|BUILD_') \
 --env ELECTRON_CACHE="/root/.cache/electron" \
 --env ELECTRON_BUILDER_CACHE="/root/.cache/electron-builder" \
 -v ${PWD}:/project \
 -v ${PWD##*/}-node-modules:/project/node_modules \
 -v ~/.cache/electron:/root/.cache/electron \
 -v ~/.cache/electron-builder:/root/.cache/electron-builder \
 electronuserland/builder:wine
```

build the image like:

```
docker build -t registry.gitlab.com/cryptoadvance/specter-desktop/electron-builder:latest .
docker push registry.gitlab.com/cryptoadvance/specter-desktop/electron-builder:latest
```