This Dockerimage is manually created and uploaded:

```
docker build -t registry.gitlab.com/cryptoadvance/specter-desktop/python:3.8.5-bionic .
docker push registry.gitlab.com/cryptoadvance/specter-desktop/python:3.8.5-bionic
```

The reason for this image is explained in [#356](https://github.com/cryptoadvance/specter-desktop/issues/356). The Dockerfile is more or less created like this:

```
curl https://raw.githubusercontent.com/docker-library/python/9ff5f04241c7bcb224303ff8cea9434e9976f8af/3.8/buster/Dockerfile > Dockerfile
sed -i -e "s/FROM buildpack-deps:buster/FROM buildpack-deps:bionic/" Dockerfile
sed -i -e '15 a # fixing tzdata' Dockerfile
sed -i -e '16 a ENV TZ=Europe/Berlin' Dockerfile
sed -i -e '17 a RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone' Dockerfile
```

Check [this Directory](../python-build) for how this image is used.