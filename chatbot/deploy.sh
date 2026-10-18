#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Source deployment configuration from .deploy/env if present.
# This file is gitignored and should contain CHATBOT_* env vars.
if [[ -f .deploy/env ]]; then
    # shellcheck disable=SC1091
    set -a; source .deploy/env; set +a
fi

# Build and deploy this checkout into the existing website resources.
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; sys.exit("Python 3.12 or newer is required.") if sys.version_info < (3, 12) else None'
node -e 'const [major,minor]=process.versions.node.split(".").map(Number); if(major<20||(major===20&&minor<9)){console.error("Node.js 20.9 or newer is required.");process.exit(1)}'
command -v npm >/dev/null
mkdir -p .deploy
chmod 700 .deploy
if [[ ! -x .deploy/venv/bin/python ]]; then
    "$PYTHON" -m venv .deploy/venv
fi
.deploy/venv/bin/python -m pip install --disable-pip-version-check --quiet -r backend/lambda/requirements.txt
exec .deploy/venv/bin/python backend/deploy.py "$@"
