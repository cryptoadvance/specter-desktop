An image used to run the build on cirrus (tests only, not cypress-tests).

Create it like this:

```
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/cirrus-jammy:20230206
docker push registry.gitlab.com/cryptoadvance/specter-desktop/cirrus-jammy:20230206
```

Check the `.cirrus.yml` on how this is used and update the $current_date there.
