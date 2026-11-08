#!/bin/sh
# One-time setup: creates .venv on Python 3.11 and installs pinned dependencies.
set -e
if command -v uv >/dev/null 2>&1; then
  uv venv --python 3.11 .venv
  uv pip install --python .venv/bin/python -r requirements.txt
  uv pip install --python .venv/bin/python --no-deps -r requirements-nodeps.txt
else
  python3.11 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/pip install --no-deps -r requirements-nodeps.txt
fi
echo "Done. Activate with: source .venv/bin/activate"
