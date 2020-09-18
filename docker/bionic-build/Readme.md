This Dockerimage is manually created and uploaded:

```
docker build -t registry.gitlab.com/cryptoadvance/specter-desktop/bionic-build:latest .
docker push registry.gitlab.com/cryptoadvance/specter-desktop/bionic-build:latest
```

The reason for this image is explained in [#356](https://github.com/cryptoadvance/specter-desktop/issues/356).