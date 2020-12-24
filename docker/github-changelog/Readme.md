An image used to create changelogs.

Create it like this:

``` 
docker build . -t registry.gitlab.com/cryptoadvance/specter-desktop/github-changelog:latest
docker push registry.gitlab.com/cryptoadvance/specter-desktop/github-changelog:latest
```

Use it like this:

```
latest_version=v0.8.1
export GH_TOKEN=YourTokenHere
docker run 4a3dd375832d  --github-token $GH_TOKEN --branch master cryptoadvance specter-desktop $latest_version > docs/new_release_notes.md
cp docs/release-notes.md docs/release-notes.md.orig
cat docs/new_release_notes.md docs/release-notes.md.orig >  docs/release-notes.md
rm docs/release-notes.md.orig docs/new_release_notes.md

```
# This will print out links to all PRs in order to review better

```	
docker run 4a3dd375832d -m --github-token $GH_TOKEN --branch master cryptoadvance specter-desktop $latest_version > docs/new_release_notes.md
```
