#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the MingLi Agent core runtime.
# Prepares the Python virtualenv, installs the package with dev+api extras,
# and builds the offline PWA (browser runtime + static bundle).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# System dependency required to create Python virtualenvs on the default image.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

# Python virtualenv (recreated only when missing).
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev,api]"
.venv/bin/python -m pip check

# Offline PWA: dependencies, pinned browser runtime, and static build.
if command -v npm >/dev/null 2>&1; then
  (
    cd web/pwa
    npm ci
    MINGLI_PWA_RUNTIME_CACHE="${MINGLI_PWA_RUNTIME_CACHE:-$REPO_ROOT/.cache/mingli-pwa-runtime}" \
      "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/scripts/build_pwa_runtime.py"
    npm run build
  )
fi

echo "MingLi Agent environment ready. Activate with: source .venv/bin/activate"
