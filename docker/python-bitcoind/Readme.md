This Dockerimage is manually created and uploaded:

```
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:v22.0
docker push registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:v22.0
```
Here the version is v23.0 but that's just an example. This folder just explains how the image is created. Which image is USED is specified:

* In the case of tests in pyproject.toml in the addopts-line (MIGHT be different in different branches)
* in the case of running 

```
python3 -m cryptoadvance.specter bitcoind #it's using "latest"
```

but you can override like this:

```
python3 -m cryptoadvance.specter bitcoind --docker-tag v22.0
```
