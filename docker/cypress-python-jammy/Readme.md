
An image, ready to be used with cypress but also provides all the dependencies we need for testing specter-desktop.
Use versions of cypress as the version part of the tag. So e.g.:

```
docker build . -t ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy:20260411
docker push ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy:20260411
```

Search for `cypress-python` on where this is used in the project.
