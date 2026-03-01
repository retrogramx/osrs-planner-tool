# Lesson 1.1: Your First Python Project

## Files
- `pyproject.toml` — project configuration and dependencies
- `src/osrs_planner/__init__.py` — makes the directory a Python package

---

## `pyproject.toml`
- Single config file for a modern Python project — replaces older `setup.py` + `requirements.txt`
- Uses TOML format — fields must be under section headers like `[project]`, `[build-system]`
- `[project]` — name, version, dependencies, authors, python version
- `[build-system]` — tells `pip` *how* to build/install your package (e.g., hatchling)
- `[tool.*]` — config for other tools like pytest, ruff, hatch
- `authors` uses table format: `[{name = "Retro"}]`, not just `["Retro"]` (PEP 621)

## `src/` layout
- `src/` is a container folder, NOT part of your package name
- `import osrs_planner` works — Python doesn't see `src/`
- Prevents a subtle bug: without `src/`, Python can import your code *without installing it*, hiding real packaging issues
- With hatchling, you tell it where to look: `packages = ["src/osrs_planner"]`

## `__init__.py`
- An empty file that tells Python "this directory is a package"
- Without it, `import osrs_planner` won't work

## Virtual environments
- `python3 -m venv venv` — creates an isolated Python environment in a `venv/` folder
- `source venv/bin/activate` — activates it (your prompt shows `(venv)`)
- Keeps your project's dependencies separate from your system Python

## Editable install
- `pip install -e .` — installs your package in "editable" mode
- The `-e` means changes to your source code take effect immediately without reinstalling
- The `.` means "install the project in the current directory"

## References
- **pyproject.toml**: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ — official guide to the format
- **PEP 621**: https://peps.python.org/pep-0621/ — the standard for `[project]` metadata
- **src layout**: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ — why use `src/`
- **Virtual environments**: https://docs.python.org/3/library/venv.html — `venv` module docs
- **pip install -e**: https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs — editable installs explained
