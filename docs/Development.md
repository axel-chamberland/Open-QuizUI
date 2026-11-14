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
pip install -e '.[dev]'
```

The Python dependencies and the pinned Ruff version are defined in `pyproject.toml`.

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

### Formatting and release files

With the virtual environment active, run `npm ci` to install the pinned Prettier version. Then use these commands from the repository root.

```bash
npm run format        # Format source and regenerate release files
npm run format:check  # Check source and release formatting without editing files
npm run release       # Run both test suites and regenerate release files
```

Prettier formats the frontend and JavaScript tests. Ruff formats the Python source and tests, and the build runs Ruff on both generated release files. Commit any regenerated release files with the source changes that produced them. CI rebuilds the release files and checks that they match the committed copies.
