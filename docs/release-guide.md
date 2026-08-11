# Release Guide

The release pipeline runs on GitHub Actions. Pushing a version tag to `upstream` triggers `.github/workflows/release.yml`, which builds every artifact, creates a draft GitHub release, and signs `SHA256SUMS` with the Specter Signer GPG key.

## Prerequisites

- `upstream` points at `git@github.com:cryptoadvance/specter-desktop.git` (`git remote -v` should show both fetch and push).
- You are on `master` with a clean workspace and `git pull upstream master` applied.
- Release-notes PR has already merged (see [Release notes](#release-notes) below).

## Cut a release

```bash
git tag v1.13.1
git push upstream v1.13.1
```

That's it. The `Release` workflow on GitHub Actions takes it from here:

- **`release-pip`** — builds the sdist/wheel and publishes to PyPI via trusted publishing.
- **`build-specterd-{linux,windows,macos}`** — builds the `specterd` binary on each platform (macOS arm64 on the free `macos-14` runner).
- **`build-electron-{linux,windows,macos}`** — builds the Electron apps using each platform's `specterd` artifact. Windows uses the public `electronuserland/builder:wine` image; macOS signs + notarizes if `APPLE_CERTIFICATE_BASE64` et al. are configured.
- **`create-release`** — collects all artifacts, generates `SHA256SUMS`, signs it with the GPG key from the `GPG_PRIVATE_KEY` secret, generates a release body (with auto-generated "What's Changed" via `gh api .../generate-notes`), and creates a **draft** GitHub release.
- **`trigger-docker`** — POSTs a repository-dispatch to `lncm/docker-specter-desktop` so Aaron's Docker build picks up the new tag (needs `AARON_TRIGGER` secret; skipped otherwise).

The release lands as a draft — review and publish it manually on GitHub.

### Required secrets

| Secret                             | Purpose                                                      |
|------------------------------------|--------------------------------------------------------------|
| `GPG_PRIVATE_KEY`                  | ASCII-armored private key for signing `SHA256SUMS`           |
| `GPG_PASSPHRASE`                   | Passphrase for the above                                     |
| `APPLE_CERTIFICATE_BASE64`         | Developer ID cert for macOS signing (optional — unsigned fallback) |
| `APPLE_CERTIFICATE_PASSWORD`       | p12 password                                                 |
| `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` | Apple notarization credentials          |
| `APPLE_PROVISIONING_PROFILE_BASE64`| Optional provisioning profile                                |
| `AARON_TRIGGER`                    | PAT for triggering `lncm/docker-specter-desktop`             |

PyPI publishing uses trusted publishing (OIDC) — no secret required.

## Release notes

Update `docs/release-notes.md` via a normal PR before tagging. Use the GitHub API or `gh` to pull "What's Changed" between the previous tag and `master`, prepend a heading, and open a PR. The `create-release` workflow job also appends auto-generated notes to the release body.

## GitHub pages download page

`./utils/generate_downloadpage.sh` still generates the `specter-static` website's download page off `utils/templates/`. Clone `specter-static` alongside `specter-desktop` and run:

```bash
./utils/generate_downloadpage.sh
```

The script installs the markdown prerequisite, regenerates the GH-page and download page, asks whether to replace/update the GitHub release page for the latest version, and offers to commit/push the static-site changes.

## Troubleshooting

If something fails mid-pipeline, re-running individual jobs is safe — they `actions/download-artifact` from prior jobs and overwrite existing release assets via `softprops/action-gh-release`. If the draft release already has assets from a stale run, delete the draft and re-run `create-release`.

macOS builds are the most likely to fail due to Apple signing/notarization glitches. The workflow falls back to unsigned builds when `APPLE_CERTIFICATE_BASE64` is empty — useful for smoke-testing the pipeline on forks.
