
An image, ready to be used with cypress but also provides all the dependencies we need for testing specter-desktop.

```
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/cypress-python
docker push registry.gitlab.com/cryptoadvance/specter-desktop/cypress-python
```