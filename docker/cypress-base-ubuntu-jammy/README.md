A base-image used in cypress-python to use a newer ubuntu focal rather than a buster.

Create it like this:

``` 
docker build . -t registry.gitlab.com/c8527/specter/cypress-base-ubuntu-jammy:latest
docker push registry.gitlab.com/c8527/specter/cypress-base-ubuntu-jammy:latest
```

used in cypress-python

