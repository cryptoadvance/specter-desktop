# AGENTS.md — Specter Desktop

Guidelines for AI contributors working on specter-desktop.

## Project Overview

Specter Desktop is a GUI for Bitcoin Core & Electrum optimized for airgapped hardware wallets. It's a Flask web app that manages multisig wallets, coordinates hardware wallet signing via HWI, and handles PSBT-based transaction workflows.

**Authors:** Stepan Snigirev (@niccokunzmann) + k9ert  
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

## Testing

Tests require a `bitcoind` binary (regtest mode). No tests run without it.

```bash
# Install bitcoind for tests
./tests/install_noded.sh --bitcoin binary  # downloads binary
# OR
./tests/install_noded.sh --bitcoin compile  # compiles from source

# Install test dependencies
pip3 install -e ".[test]"

# Run tests
pytest                          # all tests (needs bitcoind)
pytest -m "not slow"            # skip slow tests
pytest -m "not elm"             # skip Elements/Liquid tests
pytest tests/test_specter.py    # specific file
pytest --capture=no --log-cli-level=DEBUG  # verbose output
```

**Cypress (frontend tests):**
```bash
./utils/test-cypress.sh run     # run all
./utils/test-cypress.sh open    # interactive mode
```

**Important test quirks:**
- bitcoind starts once for all tests — blockchain state accumulates
- Halving interval is 150 blocks in regtest; 100 blocks needed for spendable coins
- Transaction IDs change depending on whether you run tests alone or together
- Don't hardcode txids in assertions across test suites

## Code Style

- **Black** for Python formatting. Pre-commit hook: `pre-commit install`
- CI runs a Black linter check (`.github/workflows/zblack.yml`) — currently failing
- Plain JavaScript, no frameworks. Material Icons for UI.
- Colors: orange `#F5A623`, blue `#4A90E2`
- Minimize dependencies — security-conscious project

## Building Releases

Desktop builds use PyInstaller + Electron:

1. **specterd** (daemon binary): `pyinstaller specterd.spec` from `pyinstaller/` dir
2. **Electron app**: wraps specterd, downloads it on first launch with SHA256 + GPG verification
3. Platform scripts: `utils/build-osx.sh`, `utils/build-win.sh`, etc.
4. pip package: `python3 setup.py sdist bdist_wheel`

See `docs/build-instructions.md` and `docs/continuous-integration.md` for details.

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
| CI workflows | `.github/workflows/` |
| Build scripts | `pyinstaller/`, `utils/`, `electron/` |

## Current State (as of 2026-02)

- **~259 open issues**, many from 2023 (potentially stale)
- **10 open PRs** (need assessment)
- **CI broken** — Black linter workflow fails on `master`
- **Last release:** v2.1.1 (2025-01-03)
- **Goal:** Revive with biweekly tested releases, triage issues, fix CI

## Contributing

1. Fork → branch from `master` → PR
2. Run `pre-commit install` for Black formatting
3. Reference issues in commits: `Fixes #123`
4. See `CONTRIBUTING.md` for full guidelines
