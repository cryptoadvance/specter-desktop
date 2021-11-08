An image used to run the build on cirrus (tests only, not cypress-tests).

Create it like this:

```
current_date=$(date +"%Y%m%d")
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/cirrus-focal:${current_date}
docker push registry.gitlab.com/cryptoadvance/specter-desktop/cirrus-focal:${current_date}
# Do not forget to update the $current_date in .cirrus.yml
```

Check the `.cirrus.yml` on how this is used and update the $current_date there.