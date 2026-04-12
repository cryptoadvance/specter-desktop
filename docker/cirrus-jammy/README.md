An image used to run the build on cirrus (tests only, not cypress-tests).

Create it like this:

```
docker buildx build --platform linux/amd64 -t ghcr.io/cryptoadvance/specter-desktop/cirrus-jammy:20260412 --load .
docker push ghcr.io/cryptoadvance/specter-desktop/cirrus-jammy:20260412
```

Check the `.cirrus.yml` on how this is used and update the $current_date there.
