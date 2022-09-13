A base-image used in cypress-python to use a newer ubuntu jammy rather than a buster.

Create it like this:

``` 
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/cypress-base-ubuntu-jammy:20220908
docker push registry.gitlab.com/cryptoadvance/specter-desktop/cypress-base-ubuntu-jammy:20220908
```

used in cypress-python

