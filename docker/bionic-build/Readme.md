This Dockerimage is manually created and uploaded:

```
docker build -t registry.gitlab.com/cryptoadvance/specter-desktop/bionic-build:latest .
docker push registry.gitlab.com/cryptoadvance/specter-desktop/bionic-build:latest
```

The reason for this image is explained in [#356](https://github.com/cryptoadvance/specter-desktop/issues/356) and introduced in https://github.com/cryptoadvance/specter-desktop/pull/396/files .

It has been replaced with introducing the electron-build with `registry.gitlab.com/cryptoadvance/specter-desktop/electron-builder:latest` in https://github.com/cryptoadvance/specter-desktop/pull/473/files .