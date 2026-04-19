# AGENTS.md — Specter Desktop

Guidelines for AI contributors working on specter-desktop.

## Project Overview

Specter Desktop is a GUI for Bitcoin Core & Electrum optimized for airgapped hardware wallets. It's a Flask web app that manages multisig wallets, coordinates hardware wallet signing via HWI, and handles PSBT-based transaction workflows.

**License:** MIT
**Stack:** Python 3.9-3.10, Flask, Jinja2 templates, plain JavaScript (no frameworks), JSON file persistence, PyInstaller for desktop builds
**Status:** Reviving. Last release v2.1.1 (2025-01-03). Release pipeline recently migrated to GitHub Actions. See "Current State" section at the bottom.

## Architecture (Quick Reference)

```
src/cryptoadvance/specter/
├── server.py          # Flask app factory, create_and_init()
├── cli/               # CLI entry point (specter command)
├── managers/           # Core business logic
│   ├── device_manager.py    # Hardware wallet device registry
│   ├── wallet_manager.py    # Wallet CRUD + balance/tx tracking
│   ├── node_manager.py      # Bitcoin Core / Electrum connections
│   └── user_manager.py      # Auth + RBAC
├── rpc.py             # Bitcoin Core JSON-RPC client
├── persistence.py     # JSON file storage (no SQL)
├── device.py          # Device domain model + HWI glue
├── wallet/            # Wallet domain logic, descriptors, address/tx helpers
├── util/
│   └── psbt.py        # PSBT utilities (parse, analyze, finalize)
├── devices/
│   └── hwi/           # HWI-based hardware wallet drivers (Jade, KeepKey, DIY)
├── hwi_rpc.py         # HWI JSON-RPC wrapper
├── hwi_server.py      # HWI bridge subprocess (for GUI builds)
├── templates/         # Jinja2 HTML templates
├── static/            # CSS/JS/images
└── services/          # Extension system (specterext namespace packages)
```

**Key patterns:**
- Manager pattern: each domain has a `*Manager` class that owns the lifecycle
- JSON file persistence in `~/.specter/` (devices, wallets, nodes as JSON files)
- Extensions via `specterext` namespace packages with their own Flask blueprints
- HWI bridge for hardware wallet communication (Trezor, Ledger, ColdCard, etc.)
- PSBT workflow: construct → sign (hardware) → broadcast

## Running from Source

```bash
# Prerequisites (Ubuntu/Debian)
sudo apt install libusb-1.0-0-dev libudev-dev libffi-dev libssl-dev build-essential

# Clone and set up
git clone https://github.com/cryptoadvance/specter-desktop.git
cd specter-desktop
pip3 install virtualenv
virtualenv --python=python3.10 .env
source .env/bin/activate
pip3 install -r requirements.txt --require-hashes
pip3 install -e .

# Run dev server
python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
# → http://127.0.0.1:25441/
```

**Python version:** 3.9 or 3.10 required. 3.11+ will break on some dependencies.

## CI/CD

**GitHub Actions only.** Cirrus CI and GitLab CI were retired in 2026-Q2 — see `docs/ci-migration-evidence.md` for the cutover evidence and `docs/continuous-integration.md` for the active topology.

### Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| Tests | `test.yml` | PR, push | pytest + Cypress + extension smoketest (3 jobs) |
| Release | `release.yml` | Tag push `v*` | pip + specterd + Electron for Linux/Win/macOS + GPG-sign `SHA256SUMS` |
| Black Linter | `zblack.yml` | PR, push | `psf/black@26.3.0` action pinned to Black 22.3.0, python-3.12 |
| TOC Generator | `toc.yml` | Push on `docs/**` | Auto-generates TOCs for `README.md`, `docs/faq.md`, `docs/development.md` |
| Docker Push | `docker-push.yml` | Push to master | Multi-arch image → `ghcr.io/cryptoadvance/specter-desktop:<branch>` |
| Docker Tag | `docker-tag.yml` | Release published | Multi-arch image → `ghcr.io/cryptoadvance/specter-desktop:<tag>` |
| Extension Compat | `extension-compat.yml` | PR touching `requirements.*`/`pyproject.toml` | Installs full lock, imports every bundled extension, runs `pip check` |
| specterd Build Smoke | `test-specterd-build.yml` | PR touching `pyinstaller/`, `requirements*`, `src/**` | Builds specterd on Linux and runs `--help` |
| Electron Smoke | `electron-smoketest.yml` | PR touching `pyinstaller/electron/**` | Smoke test Electron packaging |

All workflows use public GitHub-hosted runners (`ubuntu-latest` / `ubuntu-22.04` / `windows-latest` / `macos-14`). **No private runners.**

### Test workflow — `test.yml`

Three jobs on `ubuntu-22.04`:
1. **`test`** — pytest with `--cov=cryptoadvance`, 45-min timeout. Installs system deps inline; no custom image. Caches bitcoind/elementsd via `actions/cache@v4` keyed on `runner.os × runner.arch × hash(pyproject.toml, install_noded.sh, bitcoin_SHA256SUMS, elements_SHA256SUMS)` with `save-always: true`.
2. **`cypress`** — `./utils/test-cypress.sh --debug run` inside `ghcr.io/cryptoadvance/specter-desktop/cypress-python-jammy@sha256:<digest>`, 30-min timeout, `--shm-size=2g`.
3. **`extension-smoketest`** — byte-compatible port of the old Cirrus smoketest, 15-min timeout.

`tests/install_noded.sh` GPG-verifies upstream `SHA256SUMS.asc` and checks tarball SHA256 against the committed trust anchors on every run (cold cache AND cache hit).

### Release pipeline — `.github/workflows/release.yml`

Triggers on tags matching `v[0-9]+.[0-9]+.[0-9]+` (and `-*` suffixes for pre-releases). Runs entirely on **GitHub-hosted runners** — no private hardware required.

**Python version:** pinned to `3.10` via the `PYTHON_VERSION` env var at the top of `release.yml`.

**Jobs (10 total):**

1. **`release-pip`** — Builds the pip package and publishes to PyPI via **trusted publishing** (no `TWINE_PASSWORD` secret needed when configured on PyPI; falls back to token auth otherwise). Only publishes when `github.repository == 'cryptoadvance/specter-desktop'`. Version derived from tag with `-pre` → `rc` PEP 440 mapping.
2. **`build-specterd-linux`** — PyInstaller build on `ubuntu-latest`. Produces `specterd-<version>-x86_64-linux-gnu.zip`.
3. **`build-specterd-windows`** — PyInstaller build on `windows-latest`. Produces `specterd-<version>-win64.zip`. Installs `colorama` (Windows-only transitive dep of click that isn't in the lock file).
4. **`build-specterd-macos`** — PyInstaller build on `macos-14` (Apple Silicon). Produces `specterd-<version>-osx_arm64.zip`. **x86_64 macOS build is commented out** — requires a paid runner (`macos-15-large`); will be enabled when the org has a paid plan.
5. **`build-electron-linux`** — Needs `build-specterd-linux`. Downloads specterd artifact, wraps in Electron, produces `specter_desktop-<version>-x86_64-linux-gnu.tar.gz`.
6. **`build-electron-windows`** — Needs `build-specterd-windows`. Runs in `electronuserland/builder:wine` container on `ubuntu-latest`. Produces `Specter-Setup-<version>.exe`.
7. **`build-electron-macos`** — Needs `build-specterd-macos`. Universal-ish build on `macos-14`. **Code signing is conditional**: if `APPLE_CERTIFICATE_BASE64` secret is set, imports cert into a temporary keychain and signs; otherwise builds unsigned. Removes hardcoded provisioning profile from `package.json` on the fly.
8. **`create-release`** — Gathers all artifacts, computes combined `SHA256SUMS`, creates the GitHub Release, uploads binaries.
9. **`trigger-docker`** — Triggers the `docker-tag.yml` workflow for the release tag (builds and pushes the Docker image).

**Release artifacts per version:**
- `cryptoadvance.specter-<version>.tar.gz` (pip package, published to PyPI)
- `specterd-<version>-x86_64-linux-gnu.zip` (Linux daemon)
- `specterd-<version>-win64.zip` (Windows daemon)
- `specterd-<version>-osx_arm64.zip` (macOS daemon, Apple Silicon)
- `specter_desktop-<version>-x86_64-linux-gnu.tar.gz` (Linux Electron app)
- `Specter-Setup-<version>.exe` (Windows Electron app)
- macOS Electron app (produced by `build-electron-macos`)
- `SHA256SUMS` (combined checksums, created by `create-release`)

**macOS builds are now automated** (Apple Silicon free tier). x86_64 macOS requires a paid runner and is disabled.

### Release-related secrets (GitHub)

| Secret | Purpose | Required? |
|----------|---------|---|
| `GPG_PRIVATE_KEY` + `GPG_PASSPHRASE` | Sign `SHA256SUMS` | Required for signed releases |
| `APPLE_CERTIFICATE_BASE64` + `APPLE_CERTIFICATE_PASSWORD` | macOS signing cert | Optional — unsigned build if missing |
| `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID` | macOS notarization | Required with signing |
| `APPLE_PROVISIONING_PROFILE_BASE64` | Provisioning profile | Optional |
| `AARON_TRIGGER` | Trigger `lncm/docker-specter-desktop` build | Optional — skips Docker trigger if missing |
| PyPI trusted publisher | Configured on PyPI side, not a GH secret | Required for `release-pip` upstream |

### Testing a release on a fork

1. Fork `cryptoadvance/specter-desktop` on GitHub.
2. Push a tag matching `v*.*.*` or `v*.*.*-*` on your fork → `release.yml` fires automatically.
3. The `release-pip` PyPI publish step is gated on `github.repository == 'cryptoadvance/specter-desktop'`, so forks build the pip package but don't publish.
4. Unsigned macOS builds work out of the box; signing requires you to add your own Apple secrets.

## Testing

Tests require a `bitcoind` binary (regtest mode). No tests run without it.

```bash
# Install bitcoind for tests
./tests/install_noded.sh --bitcoin binary  # downloads binary
# OR
./tests/install_noded.sh --bitcoin compile  # compiles from source

# For Elements/Liquid tests (optional):
./tests/install_noded.sh --elements binary

# Install test dependencies
pip3 install -e ".[test]"

# Run tests
pytest                          # all tests (needs bitcoind)
pytest -m "not slow"            # skip slow tests
pytest -m "not elm"             # skip Elements/Liquid tests
pytest -m "not elm and not slow" # skip both
pytest tests/test_specter.py    # specific file
pytest tests/test_specter.py -k Manager  # match test name
pytest --capture=no --log-cli-level=DEBUG  # verbose output
pytest --bitcoind-log-stdout    # include bitcoind logs
```

**Cypress (frontend tests):**
```bash
npm ci                          # install JS dependencies first
./utils/test-cypress.sh run     # run all
./utils/test-cypress.sh open    # interactive mode
./utils/test-cypress.sh snapshot spec_empty_specter_home.js  # create baseline
./utils/test-cypress.sh dev spec_empty_specter_home.js       # dev against snapshot
```

**Important test quirks:**
- bitcoind starts once for all tests — blockchain state accumulates
- Halving interval is 150 blocks in regtest; 100 blocks needed for spendable coins
- Transaction IDs change depending on whether you run tests alone or together
- Don't hardcode txids in assertions across test suites
- You need Python 3.10 virtualenv for tests (`ignore_cleanup_errors` kwarg fails on 3.9)

## Code Style

- **Black** for Python formatting (v22.3.0). Pre-commit hook: `pre-commit install`
- CI runs a Black linter check (`.github/workflows/zblack.yml`) — currently failing
- Plain JavaScript, no frameworks. Material Icons for UI.
- Colors: orange `#F5A623`, blue `#4A90E2`
- Minimize dependencies — security-conscious project

## Building Releases

Desktop builds use PyInstaller + Electron:

1. **specterd** (daemon binary): `pyinstaller specterd.spec` from `pyinstaller/` dir
2. **Electron app**: wraps specterd, downloads it on first launch with SHA256 + GPG verification
3. pip package: `python3 -m build`

Release builds live in `.github/workflows/release.yml` (triggered by tag push). See `docs/release-guide.md` for the release workflow and `docs/build-instructions.md` for step-by-step manual builds.

## Dependencies

```bash
# After changing requirements.in:
pip-compile --generate-hashes requirements.in
```

Hash-pinned requirements for reproducibility and security. Don't bypass `--require-hashes`.

## Extension System

Extensions live in `specterext` namespace packages. Each extension:
- Has its own Flask blueprint, templates, and static files
- Registers via entry points in setup.cfg
- Can add UI pages, API endpoints, and background services
- Generate a skeleton: `python3 -m cryptoadvance.specter ext gen --ext-id myext --org myorg`
- CI smoke-tests extension generation in the `extension-smoketest` job (`test.yml`)
- See `docs/extensions/` for the extension development guide

## Key Files for Navigation

| What | Where |
|------|-------|
| App factory | `src/cryptoadvance/specter/server.py` |
| CLI entry | `src/cryptoadvance/specter/cli/` |
| Config classes | `src/cryptoadvance/specter/config.py` |
| RPC client | `src/cryptoadvance/specter/rpc.py` |
| Wallet model | `src/cryptoadvance/specter/wallet/` |
| Device model | `src/cryptoadvance/specter/device.py` |
| PSBT handling | `src/cryptoadvance/specter/util/psbt.py` |
| All managers | `src/cryptoadvance/specter/managers/` |
| Templates | `src/cryptoadvance/specter/templates/` |
| Tests | `tests/` |
| CI config | `.github/workflows/` |
| Build scripts | `pyinstaller/`, `utils/`, `electron/` |
| CI Docker images | `docker/` |

## Current State (as of 2026-04)

- **Last release:** v2.1.1 (2025-01-03) — no release on the new GH Actions pipeline yet; first tagged run will exercise it end-to-end.
- **CI migration complete:** Cirrus CI and GitLab CI retired; all workflows now on GitHub Actions. See `docs/ci-migration-evidence.md`.
- **macOS automation:** now covered on Apple Silicon free tier; x86_64 macOS gated on paid runner.
- **Black linter:** reconfigured to pin python-3.12 + `psf/black@26.3.0` action + black version 22.3.0 (worked around 3.14 incompatibility). Verify green state in CI before assuming.
- **Issue/PR backlog:** refreshed counts not captured here — use `gh issue list` / `gh pr list` for current state.
- **Goal:** Revive with biweekly tested releases, shake out the new release pipeline, triage issues.

## Contributing

1. Fork → branch from `master` → PR
2. Run `pre-commit install` for Black formatting
3. Reference issues in commits: `Fixes #123`
4. See `CONTRIBUTING.md` for full guidelines
