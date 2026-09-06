# Development

## Repository Structure

The project is written in Python and uses a `pyproject.toml` file for project metadata, dependencies, and test configuration.

```text
Open-QuizUI/
├── src/
│   └── openquizui/    # Main source code
├── tests/             # Test suite
├── examples/          # Examples
├── pyproject.toml     # Project configuration and dependencies
└── README.md
```

## Local Development

Clone the repository:

```bash
git clone https://github.com/axel-chamberland/Open-QuizUI.git
cd Open-QuizUI
```

The project requires **Python 3.11 or 3.12**, matching the versions currently supported by Open WebUI.

It is recommended to use a virtual environment for development:

```bash
python -m venv .venv
```

Activate it:

**Linux / macOS:**

```bash
source .venv/bin/activate
```

**Windows:**

```powershell
.venv\Scripts\Activate.ps1
```

Install the project and its dependencies:

```bash
pip install -e .
```

The dependencies are defined in `pyproject.toml`, so there is no separate `requirements.txt` file to maintain.

## Tests

Tests are located in the `tests/` directory and use `pytest`.

Run the test suite with:

```bash
pytest
```

The pytest configuration in `pyproject.toml` automatically uses the `tests/` directory and discovers files matching `test_*.py`.

Run the test suite before submitting changes to make sure the affected functionality still works.
