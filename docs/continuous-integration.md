# Continuous Integration

Specter-Desktop runs all CI on **GitHub Actions**. Cirrus CI and GitLab CI were retired in 2026-Q2 — see `docs/ci-migration-evidence.md` for the cutover evidence.

## Workflows

| Workflow                       | File                                            | Trigger                                      |
|--------------------------------|-------------------------------------------------|----------------------------------------------|
| Lint (black)                   | `.github/workflows/zblack.yml`                  | PR, push, merge queue                        |
| Tests (pytest + Cypress + extension smoketest) | `.github/workflows/test.yml`    | PR, push, merge queue                        |
| Release                        | `.github/workflows/release.yml`                 | Tag push (`v*`)                              |
| Electron smoketest             | `.github/workflows/electron-smoketest.yml`      | PR and push to master on `pyinstaller/electron/**` |
| Extension compatibility        | `.github/workflows/extension-compat.yml`        | PR; push on `requirements.*` / `pyproject.toml`; `workflow_dispatch` |
| Specterd build smoke           | `.github/workflows/test-specterd-build.yml`     | PR                                           |
| Docker image push              | `.github/workflows/docker-push.yml`             | Push to any branch except `gh-readonly-queue/**` |
| Docker image tag               | `.github/workflows/docker-tag.yml`              | Tag push (`v*`)                              |
| Docs table of contents         | `.github/workflows/toc.yml`                     | Push (branches except `gh-readonly-queue/**`, tags) |

## Test workflow

`test.yml` has three jobs, all on `ubuntu-22.04`:

- **`test`** — pytest with `--cov=cryptoadvance`. Runs in 45 min. Installs system deps inline; no custom image. Caches bitcoind/elementsd binaries via `actions/cache@v4` keyed on `runner.os × runner.arch × hash(pyproject.toml, tests/install_noded.sh, tests/bitcoin_SHA256SUMS, tests/elements_SHA256SUMS)`.
- **`cypress`** — runs `./utils/test-cypress.sh --debug run` inside `ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy@sha256:<digest>`. 30-minute timeout. `--shm-size=2g` to avoid Cypress OOMs on the default 64 MB `/dev/shm`. Shares the bitcoind/elements cache with `test`.
- **`extension-smoketest`** — byte-compatible port of the former Cirrus smoketest. 15 min. Smoke-tests `ext gen`, server boot, and log-line / curl assertion. Contract must stay stable — downstream extension developers depend on it.

All three jobs use `actions/checkout@v4` with `fetch-depth: 0` so `git describe` resolves annotated tags for `tests/test_util_version.py`.

## Merge queue

`master` uses a GitHub merge queue. Every queued pull request is tested as part of a temporary `gh-readonly-queue/master/pr-<n>-<sha>` branch, so required checks must also be reported on that ref.

Required status checks (branch protection): `test`, `cypress`, `extension-smoketest`, `black`. For those checks to appear on a merge-group commit, the workflows producing them must trigger on `merge_group`:

- `test.yml` — `merge_group: types: [checks_requested]`
- `zblack.yml` — `merge_group`

Two workflows are explicitly excluded from `gh-readonly-queue/**` pushes because they react to *every* branch push:

- `docker-push.yml` would otherwise push a throw-away ghcr.io image per queue entry.
- `toc.yml` would otherwise commit generated TOCs onto a temporary queue ref.

Path-filtered workflows (`extension-compat.yml`, `test-specterd-build.yml`, `electron-smoketest.yml`) intentionally carry no `merge_group` trigger: `paths` filtering is not supported for that event, and none of their jobs are required checks. If one of them is ever promoted to a required check, add the trigger and drop the `paths` filter — otherwise the queue stalls.

## Caching

`actions/cache@v4` with `save-always: true` on a key that includes `runner.arch` (prevents ARM/x86 cache poisoning). The key hashes the committed `tests/bitcoin_SHA256SUMS` and `tests/elements_SHA256SUMS` trust anchors — bumping a version in `pyproject.toml` rotates the cache via those files.

### Binary verification

`tests/install_noded.sh` GPG-verifies the upstream `SHA256SUMS.asc` against the Bitcoin Core and Elements release signing keys, and checks the tarball SHA256 against the committed trust anchors on every run (cold cache AND cache hit). A tampered cache entry fails closed on restore. See PR #2606 for the threat model.

## Cypress container

`ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy` is pinned by digest (not tag) in `test.yml`. This makes Dockerfile edits visibly require a workflow bump. When editing `docker/cypress-python-jammy/Dockerfile`, rebuild and push to GHCR with a fresh tag, then update the digest pin.

## Release pipeline

See [`release-guide.md`](./release-guide.md). Pushing a tag matching `v[0-9]+.[0-9]+.[0-9]+[-*]?` triggers `release.yml`, which builds pip/specterd/Electron artifacts for Linux/Windows/macOS, signs `SHA256SUMS`, and creates a draft GitHub release. Docker images are built by `lncm/docker-specter-desktop` (triggered via `AARON_TRIGGER` secret).

## Flake policy

- Cypress: `retries: { runMode: 1, openMode: 0 }`. Specs retry-to-green emit a warning annotation.
- pytest: `--reruns 0` (fail fast). Flakes are debt, not a coping mechanism.
- Spec flagged flaky twice in 14 days gets `@skip(reason="flaky", issue="#NNNN")` with a 2-week SLA.

## Secrets

| Secret                    | Used by                  | Purpose                                      |
|---------------------------|--------------------------|----------------------------------------------|
| `GITHUB_TOKEN`            | (auto-provided)          | Checkout, artifact upload, ghcr.io push      |
| `GPG_PRIVATE_KEY` + `GPG_PASSPHRASE` | `release.yml` | Sign `SHA256SUMS`                            |
| `APPLE_*` (six)           | `release.yml` macOS      | Code signing + notarization (optional)       |
| `AARON_TRIGGER`           | `release.yml`            | Trigger `lncm/docker-specter-desktop` build  |

No GitLab secrets remain.
