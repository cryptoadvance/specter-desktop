# Contributing to Specter Desktop

Specter Desktop is an Open Source Project under the MIT License and everyone is invited to contribute to it.

We haven't created many explicit processes and rely on the best practices of Open Source projects. If you want to contribute, fork the project and create a PR.

## Table of Contents

- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Finding Help](#finding-help)
- [Contributors and Maintainers](#contributors-and-maintainers)

## How to Contribute

To contribute code:

1. **Fork the repository** on GitHub
2. **Create a branch** from `master` (or the relevant branch)
   ```bash
   git checkout -b your-feature-branch
   ```

3. **Make your changes**
   - Follow our [Code Standards](#code-standards)
   - Write or update tests as needed
   - Update documentation if necessary

4. **Test your changes**
   - Run the test suite (see [Testing](#testing))
   - Ensure all tests pass

5. **Commit your changes**
   - Write clear, descriptive commit messages
   - If addressing an issue, reference it in your commit message: `Fixes #123` or `Closes #123`

6. **Push to your fork** and create a Pull Request

## Development Setup

For detailed development setup instructions, see [docs/development.md](docs/development.md).

Quick start:

1. **Install dependencies** (see [docs/development.md](docs/development.md) for platform-specific instructions)

2. **Set up virtual environment**
   ```sh
   git clone https://github.com/cryptoadvance/specter-desktop.git
   cd specter-desktop
   pip3 install virtualenv
   virtualenv --python=python3 .env
   source .env/bin/activate  # On Windows: .env\Scripts\activate
   pip3 install -r requirements.txt --require-hashes
   pip3 install -e .
   ```

3. **Run the development server**
   ```sh
   python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
   ```
   Specter will be available at http://127.0.0.1:25441/

**Note**: Specter currently supports Python 3.9 and 3.10.

## Code Standards

### Python Code Style

- **Use Black** for code formatting. We have a pre-commit hook to automate this:
  ```bash
  pre-commit install
  ```
  This will automatically format your code before commits.

### Frontend

- We prefer plain JavaScript over frameworks
- Use Material Icons from https://material.io/resources/icons/?style=baseline
- Color scheme:
  - Orange: `#F5A623`
  - Blue: `#4A90E2`

### Dependencies

- **Minimize dependencies** - We're security-conscious and prefer fewer dependencies
- If you update `requirements.in`, generate the new `requirements.txt`:
  ```sh
  pip-compile --generate-hashes requirements.in
  ```

## Testing

We use two testing frameworks:

### Backend Tests (pytest)

Run the test suite:
```bash
# Run all tests
pytest

# Run tests excluding slow ones
pytest -m "not slow"

# Run specific test file
pytest tests/test_specter.py

# Run specific test
pytest tests/test_specter.py::test_specter
```

**Note**: You need bitcoind for tests. See [docs/development.md](docs/development.md#how-to-run-the-tests) for setup instructions.

### Frontend Tests (Cypress)

Run Cypress tests:
```bash
# Run all Cypress tests
./utils/test-cypress.sh run

# Open Cypress app for interactive testing
./utils/test-cypress.sh open

# Run specific test with snapshot
./utils/test-cypress.sh snapshot spec_wallet_utxo.js
./utils/test-cypress.sh run spec_wallet_utxo.js
```

For more details, see [docs/cypress-testing.md](docs/cypress-testing.md).

## Finding Help

- **Documentation**: Check [docs/development.md](docs/development.md) for development setup
- **FAQ**: See [docs/faq.md](docs/faq.md) for common questions
- **Telegram**: Join our [Telegram support group](https://t.me/spectersupport) for real-time help
- **GitHub Issues**: Search existing issues or create a new one

## Contributors and Maintainers

### Contributors

Thank you very much to all our [Contributors](https://github.com/cryptoadvance/specter-desktop/graphs/contributors). See also the contributors to each specific release in the release-notes.

### Maintainers

Maintainers are the ones who can merge PRs and create tags/releases. They are listed as "authors" in `pyproject.toml` (and `setup.py`).

If it's necessary to add more formal processes, we'll probably look into Pieter Hintjens' [Social Architecture](https://hintjens.gitbooks.io/social-architecture/content/) and specifically the C4 process. Pieter explicitly mentions two roles: Contributors and Maintainers.

---

Thank you for contributing to Specter Desktop! Your contributions help make Bitcoin more accessible and secure for everyone.
