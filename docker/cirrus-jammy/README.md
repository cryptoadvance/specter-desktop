An image used to run the build on cirrus (tests only, not cypress-tests).

Create it like this:

```
docker build . -t registry.gitlab.com/relativisticelectron/specter-desktop/cirrus-jammy:latest
docker push registry.gitlab.com/relativisticelectron/specter-desktop/cirrus-jammy:latest
```

Check the `.cirrus.yml` on how this is used and update the $current_date there.
