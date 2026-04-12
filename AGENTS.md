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

The project uses **GitHub Actions** for linting, testing, Docker images, and **the full release pipeline**, plus **Cirrus CI** for the heavyweight test suite (pytest + Cypress). GitLab CI is retained in `.gitlab-ci.yml` but effectively dead — the release flow was migrated to GitHub Actions.

### Overview

| Provider | Purpose | Config File | Trigger |
|----------|---------|-------------|---------|
| **GitHub Actions** | Lint, smoke-build, Docker images, **releases** (pip + specterd + Electron for Linux/Win/macOS) | `.github/workflows/` | Push, PR, tags |
| **Cirrus CI** | Full test suite (pytest + Cypress + extension smoketest) | `.cirrus.yml` | PR |
| **GitLab CI** | **Dead** — config retained; `check` job only waits on GH master status. Release jobs no longer run. | `.gitlab-ci.yml` | (vestigial) |

### GitHub Actions (7 workflows)

1. **Black Python Linter** (`zblack.yml`) — Runs on every push and PR. Uses `psf/black@26.3.0` action pinned to Black version `22.3.0`, on python-3.12 (pinned to avoid 3.14 incompatibility with Black 22.3.0). Checks `./src`.
2. **TOC Generator** (`toc.yml`) — Auto-generates TOCs for `README.md`, `docs/faq.md`, `docs/development.md` on push.
3. **Docker Push** (`docker-push.yml`) — Builds multi-arch (amd64 + arm64) image on every push. Pushes to `ghcr.io/<owner>/<repo>:<branch>` (upstream: `ghcr.io/cryptoadvance/specter-desktop:<branch>`).
4. **Docker Tag** (`docker-tag.yml`) — Builds multi-arch image on version tags. Pushes to `ghcr.io/<owner>/<repo>:<tag>`.
5. **Extension Compatibility Check** (`extension-compat.yml`) — On changes to `requirements.*` or `pyproject.toml`: installs the full lock file, imports every bundled extension (Swan, LiquidIssuer, DevHelp, Notifications, ExFund, Faucet, Electrum, Spectrum, StackTrack, TimelockRecovery), runs `pip check`, and best-effort runs extension test suites. Catches dep conflicts before they break downstream extensions.
6. **Test specterd build** (`test-specterd-build.yml`) — PR smoke test on changes to `pyinstaller/`, `requirements*`, `src/**`, or packaging files. Builds specterd on Linux and runs `--help` smoke test.
7. **Release** (`release.yml`) — **The release pipeline.** See next section.

All GitHub Actions use public runners (`ubuntu-latest` / `ubuntu-24.04` / `windows-latest` / `macos-14`). **No private runners.**

### Cirrus CI (Testing)

Cirrus CI runs the **full test suite** on PRs. Config: `.cirrus.yml`.

**Three tasks:**
1. **`test_task`** — Full pytest suite with bitcoind + elementsd in regtest mode. Uses cached binary downloads. Produces JUnit XML results.
2. **`cypress_test_task`** — Frontend tests with Cypress. Requires 6 CPU, 6GB RAM. Produces screenshots and video artifacts.
3. **`extension_smoketest_task`** — Generates a test extension, starts the server, verifies the extension loads and responds.

**Docker images used:**
- `registry.gitlab.com/cryptoadvance/specter-desktop/cirrus-jammy:20230206` (pytest)
- `registry.gitlab.com/cryptoadvance/specter-desktop/cypress-python-jammy:20230206` (Cypress)

Both images are pre-built and hosted on the GitLab container registry. They include Python, virtualenv, and other dependencies. The `docker/` directory in the repo contains Dockerfiles for building them.

**Caching:** bitcoind and elementsd binaries are cached by Cirrus based on the version pinned in `pyproject.toml`. The `tests/install_noded.sh` script handles downloading or compiling them.

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
| `APPLE_CERTIFICATE_BASE64` | Base64-encoded `.p12` Apple signing certificate | Optional — unsigned build if missing |
| `APPLE_CERTIFICATE_PASSWORD` | Password for the `.p12` | With `APPLE_CERTIFICATE_BASE64` |
| `APPLE_PROVISIONING_PROFILE_BASE64` | Base64-encoded provisioning profile | Optional |
| PyPI trusted publisher | Configured on PyPI side, not a GH secret | Required for `release-pip` in upstream |

Historical GitLab secrets (`GH_BIN_UPLOAD_PW`, `TWINE_PASSWORD`, `GPG_PASSPHRASE`, `SSH_SPECTEREXT_DEPLOY_KEY`, `SSH_SPECTERSTATIC_DEPLOY_KEY`) are **no longer used**. `.gitlab-ci.yml` still references them but the pipeline is dead.

### Testing a release on a fork

1. Fork `cryptoadvance/specter-desktop` on GitHub.
2. Push a tag matching `v*.*.*` or `v*.*.*-*` on your fork → `release.yml` fires automatically.
3. The `release-pip` PyPI publish step is gated on `github.repository == 'cryptoadvance/specter-desktop'`, so forks build the pip package but don't publish.
4. Unsigned macOS builds work out of the box; signing requires you to add your own Apple secrets.

### Dead config

- `.gitlab-ci.yml` — still in the repo but release jobs no longer run. Safe to remove in a cleanup pass.
- `pyinstaller/build-win-ci.bat` — former GitLab Windows runner entry point; no longer invoked.
- `utils/release.sh` / `utils/release_helper.py` / `utils/github.py` — may contain dead code paths now that GitLab isn't uploading artifacts. Audit before changes.

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
3. Platform scripts: `utils/build-osx.sh`, `utils/build-unix.sh`, `pyinstaller/build-win-ci.bat`
4. pip package: `python3 -m build`

See `docs/build-instructions.md` for step-by-step manual build instructions.

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
- CI smoke-tests extension generation in `extension_smoketest_task` (Cirrus)
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
| CI config | `.github/workflows/`, `.cirrus.yml`, `.gitlab-ci.yml` |
| Build scripts | `pyinstaller/`, `utils/`, `electron/` |
| CI Docker images | `docker/` |

## Current State (as of 2026-04)

- **Last release:** v2.1.1 (2025-01-03) — no release on the new GH Actions pipeline yet; first tagged run will exercise it end-to-end.
- **CI migration complete:** release pipeline moved from GitLab to `.github/workflows/release.yml`. `.gitlab-ci.yml` retained but dead.
- **macOS automation:** now covered on Apple Silicon free tier; x86_64 macOS gated on paid runner.
- **Black linter:** reconfigured to pin python-3.12 + `psf/black@26.3.0` action + black version 22.3.0 (worked around 3.14 incompatibility). Verify green state in CI before assuming.
- **Issue/PR backlog:** refreshed counts not captured here — use `gh issue list` / `gh pr list` for current state.
- **Goal:** Revive with biweekly tested releases, shake out the new release pipeline, triage issues.

## Contributing

1. Fork → branch from `master` → PR
2. Run `pre-commit install` for Black formatting
3. Reference issues in commits: `Fixes #123`
4. See `CONTRIBUTING.md` for full guidelines
