An image used to run the build on cirrus (tests only, not cypress-tests).

Create it like this:

``` 
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/cirrus-focal:latest
docker push registry.gitlab.com/cryptoadvance/specter-desktop/cirrus-focal:latest
```

Check the `.cirrus.yml` on how this is used