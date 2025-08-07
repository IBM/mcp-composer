# 🧹 Developer Chores for `mcp-composer`

This document outlines common developer tasks (chores) to maintain code quality, security, and consistency in the `mcp-composer` project.

---

## 📦 Setup

```bash
# Recommended: use a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows

# Install all development tools
pip install -r requirements-dev.txt
```

## 🧪 Run All Chores (One-Liner)

```bash
make chore
```

### 🎨 Code Formatting - Tool black

```bash
black .
```

### 🔍 Linting - Tool: Ruff

```bash
ruff check src/ tests/
```

### To auto-fix issues:

```bash
ruff check src/ tests/ --fix
```
🧠 Type Checking - Tool: mypy

```bash

mypy src/
```


### 📊 Test Coverage - Tool: pytest + coverage.py

```bash
# Clean old data
coverage erase


# Run tests and collect coverage
export PYTHONPATH=src
coverage run --source=mcp_composer -m pytest test/

# View coverage in terminal
coverage report -m

# Generate HTML report
coverage html
open htmlcov/index.html  # Use `xdg-open` on Linux
```

### 🧪 Run Tests

```bash
pytest test/
```
### 🧼 Clean All Generated Files

```bash
rm -rf .coverage htmlcov .pytest_cache .mypy_cache
```
### 🔄 Pre-Commit Hooks (Optional)

```bash
pre-commit install
pre-commit run --all-files
```