# Development

## Repository Structure

The project consists of a Python backend and a JavaScript frontend. The `release/` directory contains generated Open WebUI functions.

```text
Open-QuizUI/
├── backend/             # Python backend and Open WebUI integration
├── frontend/            # JavaScript frontend
│   ├── assets/          # Frontend assets
│   ├── src/             # Frontend source code
│   ├── styles/          # Frontend styles
│   └── index.html       # Frontend entry point
├── release/             # Generated Open WebUI functions
│   ├── action_function.py
│   └── tool.py
├── tests/               # Python and JavaScript tests
├── examples/            # Examples
├── pyproject.toml       # Python project configuration and dependencies
├── package.json         # JavaScript development dependencies and scripts
└── package-lock.json    # Locked JavaScript dependencies
```

## Local Development

Clone the repository:

```bash
git clone https://github.com/axel-chamberland/Open-QuizUI.git
cd Open-QuizUI
```

The project requires **Python 3.11 or 3.12**, matching the versions currently supported by Open WebUI.

### Python

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

The Python dependencies are defined in `pyproject.toml`; there is no separate `requirements.txt` file to maintain.

```bash
pytest
```

### JavaScript

JavaScript tests use **Vitest**. They cover frontend logic and behaviour independently of the browser.

Run the JavaScript test suite with:

```bash
npm test
```

### Running all tests

Run both test suites with:

```bash
npm run test:all
```

Run the full test suite before submitting changes to make sure the affected functionality still works.
