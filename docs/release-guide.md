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
- **`build-specterd-{linux,windows,macos}`** — builds the `specterd` binary on each platform. macOS uses native `macos-14` (arm64) and `macos-15-intel` (x64) runners and smoke-tests each daemon before packaging.
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

## Website download page

The public downloads page is maintained in [`cryptoadvance/specter-website`](https://github.com/cryptoadvance/specter-website), not generated from this repository. Its `/downloads` page fetches published releases from the GitHub Releases API and renders the latest stable assets plus signature-verification instructions.

If download-page text, links, or signer fingerprints need to change, update the React components in `specter-website` (for example `client/src/pages/downloads.tsx` and `client/src/components/downloads/`).

## Troubleshooting

If something fails mid-pipeline, re-running individual jobs is safe — they `actions/download-artifact` from prior jobs and overwrite existing release assets via `softprops/action-gh-release`. If the draft release already has assets from a stale run, delete the draft and re-run `create-release`.

macOS builds are the most likely to fail due to Apple signing/notarization glitches. The workflow falls back to unsigned builds when `APPLE_CERTIFICATE_BASE64` is empty — useful for smoke-testing the pipeline on forks.

## Validate a release candidate on a fork

Do not create or push a tag until the candidate diff and local checks have been reviewed. Once local review is approved, use immutable pre-release tags on the selected validation fork; never move a pre-tag after GitHub Actions has tested it. The release manifest records `${{ github.repository }}`, so a fork-built app downloads its fork artifacts while the real upstream release continues to download from `cryptoadvance/specter-desktop`.

```bash
git remote get-url origin
# Confirm that origin is the intended validation fork, not upstream.
git fetch upstream master
git merge-base --is-ancestor upstream/master HEAD
git status --short --branch
git diff --check upstream/master...HEAD
cd pyinstaller/electron
npm test
cd ../..
CANDIDATE_TAG=v2.1.11-pre1
if git rev-parse --verify "refs/tags/${CANDIDATE_TAG}"; then
  echo "Tag already exists locally: ${CANDIDATE_TAG}"
  exit 1
fi
git tag "${CANDIDATE_TAG}"
git push origin "${CANDIDATE_TAG}"
```

The `-preN` tag creates a draft GitHub prerelease. PyPI publishing is disabled outside `cryptoadvance/specter-desktop`, and absent Apple/GPG secrets exercise the unsigned fork fallback; that does not validate upstream signing or notarization.

Before accepting the candidate, record the workflow run URL and verify:

- both macOS daemon jobs report the expected native architecture and pass `specterd --help`;
- `specterd-v2.1.11-preN-osx_x64.zip`, `specterd-v2.1.11-preN-osx_arm64.zip`, and `Specter-v2.1.11-preN.dmg` are present;
- `SHA256SUMS` contains those three artifacts;
- the published prerelease and embedded daemon repository point to the selected fork;
- the unsigned DMG launches, downloads, verifies, and relaunches on both a real Intel Mac and a real Apple Silicon Mac, including an upgrade with existing settings.

If the candidate changes, create `v2.1.11-pre2` (then `pre3`, and so on) at the new reviewed commit. Upstream still requires a secret-enabled signing/notarization validation before publication.
