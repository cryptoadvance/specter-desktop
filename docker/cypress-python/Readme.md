
An image, ready to be used with cypress but also provides all the dependencies we need for testing specter-desktop.
Use versions of cypress as the version part of the tag. So e.g.:
# TODO (change latest to version number)

```
docker build . -t registry.gitlab.com/relativisticelectron/specter-desktop/cypress-python:latest
docker push registry.gitlab.com/relativisticelectron/specter-desktop/cypress-python:latest
```

Search for `cypress-python` on where this is used in the project.
