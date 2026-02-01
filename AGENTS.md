# AGENTS.md — Specter Desktop

Guidelines for AI contributors working on specter-desktop.

## Project Overview

Specter Desktop is a GUI for Bitcoin Core & Electrum optimized for airgapped hardware wallets. It's a Flask web app that manages multisig wallets, coordinates hardware wallet signing via HWI, and handles PSBT-based transaction workflows.

**License:** MIT
**Stack:** Python 3.9-3.10, Flask, Jinja2 templates, plain JavaScript (no frameworks), JSON file persistence, PyInstaller for desktop builds
**Status:** Maintenance mode. Last release v2.1.1 (2025-01-03). ~259 open issues, CI partially broken.

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
├── logic/             # Domain models (Device, Wallet, PSBTView, TxList)
├── hwi/               # Hardware Wallet Interface bridge
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

The project uses **three CI providers** for different purposes, plus private GitLab runners for releases.

### Overview

| Provider | Purpose | Config File | Trigger |
|----------|---------|-------------|---------|
| **GitHub Actions** | Linting, Docker images, TOC generation | `.github/workflows/` | Push, PR |
| **Cirrus CI** | Full test suite (pytest + Cypress) | `.cirrus.yml` | PR |
| **GitLab CI** | Releasing (binaries, pip, Electron, signatures) | `.gitlab-ci.yml` | Tags only |

### GitHub Actions (4 workflows)

1. **Black Python Linter** (`.github/workflows/zblack.yml`) — Runs on every push and PR. Checks `./src` with Black 22.3.0. **Currently failing on `master`.**
2. **TOC Generator** (`.github/workflows/toc.yml`) — Auto-generates table of contents for README.md, faq.md, development.md on push.
3. **Docker Push** (`.github/workflows/docker-push.yml`) — Builds multi-arch Docker image (amd64 + arm64) on every push to any branch. Pushes to `ghcr.io/cryptoadvance/specter-desktop:<branch>`.
4. **Docker Tag** (`.github/workflows/docker-tag.yml`) — Builds multi-arch Docker image on version tags (`v*.*.*`). Pushes to `ghcr.io/cryptoadvance/specter-desktop:<tag>`.

GitHub Actions use standard public runners (`ubuntu-latest` / `ubuntu-24.04`). No private runners needed.

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

### GitLab CI (Releasing)

GitLab CI handles the **entire release pipeline**. Config: `.gitlab-ci.yml`. It mirrors the GitHub repo and triggers on tags.

**Important: GitLab uses private runners, not public shared runners.**

**Base image:** `registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:v22.0` — a custom image with Python and bitcoind pre-installed.

**Stages:**

1. **`testing`** — `check` job: Verifies all GitHub Actions tests are green before proceeding (calls `utils/release.sh wait_on_master`). The actual test jobs (`.test`, `.test-cypress`) are hidden (disabled) since testing moved to Cirrus CI.

2. **`releasing`** — Builds and uploads release artifacts:
   - **`release_pip`** — Builds pip package, uploads to PyPI (or test.pypi.org for forks), signs SHA256SUMS
   - **`release_binary_windows`** — Builds specterd Windows binary using a **Windows GitLab runner** (tag: `windows`). Uses PyInstaller via `pyinstaller/build-win-ci.bat`
   - **`release_electron_linux_windows`** — Builds Electron desktop apps for Linux and Windows. Uses the Windows specterd from the previous job. Uploads `.exe`, `.tar.gz`, and `.zip` to GitHub Releases

3. **`post_releasing`** — Final steps:
   - **`release_signatures`** — Downloads all artifacts, verifies individual SHA256SUMS signatures, creates a combined `SHA256SUMS` file, signs it, uploads to GitHub Releases
   - **`release_docker`** — Triggers Docker image build
   - **`tag_specterext_dummy_repo`** — Tags the specterext-dummy repo with the same version
   - **`update_github`** / **`update_webpage`** — Updates the GitHub release page and the static download page

**Release artifacts per version:**
- `specterd-<version>-win64.zip` (Windows daemon)
- `specterd-<version>-x86_64-linux-gnu.zip` (Linux daemon)
- `Specter-Setup-<version>.exe` (Windows Electron app)
- `specter_desktop-<version>-x86_64-linux-gnu.tar.gz` (Linux Electron app)
- `cryptoadvance.specter-<version>.tar.gz` (pip package)
- `SHA256SUMS` + `SHA256SUMS.asc` (signed checksums)
- macOS builds are **not yet automated** in CI

### Private Runner Setup

Releases are built on private runners only (build-only-on-private-hardware policy).

#### GitLab Runner (Linux)

GitLab uses a `gitlab-docker-runner` — jobs run inside Docker containers, but also need access to the Docker socket to spin up bitcoind containers.

Setup follows the [Docker socket binding](https://docs.gitlab.com/ee/ci/docker/using_docker_build.html#use-docker-socket-binding) approach. Key implications for tests:
- bitcoind gets `-rpcallowip=` for the Docker network
- Tests use the Docker network IP (not localhost) to talk to bitcoind

#### GitLab Runner (Windows)

Required for building Windows binaries. Prerequisites:
- Windows 10+ with WSL2 and Docker Desktop
- Python 3.7+, Git, Docker
- [GitLab Runner for Windows](https://docs.gitlab.com/runner/install/windows.html)

Setup:
```powershell
mkdir \Gitlab-Runner
# Download gitlab-runner-windows-amd64.exe, rename to gitlab-runner.exe
cd \Gitlab-Runner
./gitlab-runner.exe register   # Use registration token from GitLab CI/CD settings
./gitlab-runner.exe install    # Install as system service
./gitlab-runner.exe start      # Start the runner
```

Tag the runner with `windows` so release jobs can find it. Docker Desktop must be running (requires user login on the machine).

#### CI/CD Dev Environment (for testing releases)

To test the release pipeline on your own fork:

1. Fork `cryptoadvance/specter-desktop` on GitHub
2. Create a GitLab project mirroring your GitHub fork ([new CI/CD project](https://gitlab.com/projects/new#cicd_for_external_repo)) — use the **same repo name**: `specter-desktop`
3. Activate private runners, deactivate public runners (contact maintainers for access)
4. Create tokens and set as GitLab CI/CD variables:
   - `GH_BIN_UPLOAD_PW` — GitHub token for uploading release assets
   - `TWINE_PASSWORD` — [test.pypi.org](https://test.pypi.org) API token for pip uploads
5. Create a tag on your GitHub fork → watch the test release pipeline run

### GitLab CI Variables (Secrets)

| Variable | Purpose |
|----------|---------|
| `GH_BIN_UPLOAD_PW` | GitHub token for uploading release binaries |
| `TWINE_PASSWORD` | PyPI/TestPyPI API token for pip package upload |
| `GPG_PASSPHRASE` | GPG key passphrase for signing SHA256SUMS |
| `SSH_SPECTEREXT_DEPLOY_KEY` | SSH key for tagging specterext-dummy repo |
| `SSH_SPECTERSTATIC_DEPLOY_KEY` | SSH key for updating specter-static download page |

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
| Wallet model | `src/cryptoadvance/specter/logic/wallet.py` |
| Device model | `src/cryptoadvance/specter/logic/device.py` |
| PSBT handling | `src/cryptoadvance/specter/logic/psbt.py` |
| All managers | `src/cryptoadvance/specter/managers/` |
| Templates | `src/cryptoadvance/specter/templates/` |
| Tests | `tests/` |
| CI config | `.github/workflows/`, `.cirrus.yml`, `.gitlab-ci.yml` |
| Build scripts | `pyinstaller/`, `utils/`, `electron/` |
| CI Docker images | `docker/` |

## Current State (as of 2026-02)

- **~259 open issues**, many from 2023 (potentially stale)
- **10 open PRs** (need assessment)
- **CI:** Black linter failing on GitHub Actions; Cirrus CI tests and GitLab release pipeline status unknown (need verification)
- **Last release:** v2.1.1 (2025-01-03)
- **Goal:** Revive with biweekly tested releases, triage issues, fix CI

## Contributing

1. Fork → branch from `master` → PR
2. Run `pre-commit install` for Black formatting
3. Reference issues in commits: `Fixes #123`
4. See `CONTRIBUTING.md` for full guidelines
