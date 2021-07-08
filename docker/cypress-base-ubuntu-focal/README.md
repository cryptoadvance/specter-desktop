A base-image used in cypress-python to use a newer ubuntu focal rather than a buster.

Create it like this:

``` 
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/cypress-base-ubuntu-focal:latest
docker push registry.gitlab.com/cryptoadvance/specter-desktop/cypress-base-ubuntu-focal:latest
```

used in cypress-python

