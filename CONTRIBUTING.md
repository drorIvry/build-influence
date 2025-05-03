# Contributing to Build Influence

First off, thank you for considering contributing to Build Influence! We welcome any help, from reporting bugs and suggesting features to submitting code changes.

## How Can I Contribute?

### Reporting Bugs

- **Ensure the bug was not already reported** by searching on GitHub under [Issues](https://github.com/drorivry/build-influence/issues). (Replace `drorivry/build-influence` with your actual repository path if different).
- If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/drorivry/build-influence/issues/new). Be sure to include a **title and clear description**, as much relevant information as possible, and a **code sample or an executable test case** demonstrating the expected behavior that is not occurring.

### Suggesting Enhancements

- Open a new issue using the Feature Request template.
- Clearly describe the enhancement and the motivation for it.
- Explain why this enhancement would be useful.
- Provide code examples if applicable.

### Pull Requests

We actively welcome your pull requests:

1.  Fork the repo and create your branch from `main`.
2.  If you've added code that should be tested, add tests.
3.  If you've changed APIs, update the documentation.
4.  Ensure the test suite passes (`pytest tests/`).
5.  Make sure your code lints (`flake8 src/ tests/`) and is formatted (`black src/ tests/`).
6.  Ensure type checks pass (`mypy src/ tests/`).
7.  Issue that pull request!

## Development Setup

1.  Fork the repository on GitHub.
2.  Clone your fork locally:
    ```bash
    git clone git@github.com:YOUR_USERNAME/build-influence.git
    cd build-influence
    ```
3.  Create a virtual environment (recommended):
    ```bash
    python3.12 -m venv venv
    source venv/bin/activate # On Windows use `venv\Scripts\activate`
    ```
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    # Install development/testing tools if they are not in requirements.txt
    pip install black flake8 mypy pytest pytest-cov build twine
    ```

## Coding Standards

- Please follow the [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide.
- Use `flake8` for linting and `black` for formatting. Our CI pipeline checks this, so please run `flake8 src/ tests/` and `black src/ tests/` before committing.
- Use type hints (`mypy`) for static analysis. Our CI pipeline checks this.
- Write tests using `pytest` for new functionality.

## Code of Conduct

Please note that this project is released with a Contributor Code of Conduct. By participating in this project you agree to abide by its terms. (Consider adding a `CODE_OF_CONDUCT.md` file).

## Any questions?

Feel free to open an issue if you have questions about contributing.

Thank you for your contribution!
