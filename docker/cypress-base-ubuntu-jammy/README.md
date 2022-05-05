A base-image used in cypress-python to use a newer ubuntu jammy rather than a buster.

Create it like this:

``` 
docker build . -t registry.gitlab.com/relativisticelectron/specter-desktop/cypress-base-ubuntu-jammy:latest
docker push registry.gitlab.com/relativisticelectron/specter-desktop/cypress-base-ubuntu-jammy:latest
```

used in cypress-python

