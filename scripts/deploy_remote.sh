#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/deploy_remote.sh <ssh_host> [git_ref]
# Example:
#   ./scripts/deploy_remote.sh ubuntu@ops-server main

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <ssh_host> [git_ref]"
  exit 1
fi

SSH_HOST="$1"
GIT_REF="${2:-main}"
REMOTE_DIR="${REMOTE_DIR:-/srv/swap-ops-dashboard}"
SERVICE_NAME="${SERVICE_NAME:-swap-ops.service}"

echo "[deploy] host=${SSH_HOST} ref=${GIT_REF} dir=${REMOTE_DIR} service=${SERVICE_NAME}"

ssh "${SSH_HOST}" "set -euo pipefail
if [[ ! -d '${REMOTE_DIR}/.git' ]]; then
  echo '[deploy] ERROR: remote repo not found at ${REMOTE_DIR}'
  echo '[deploy] Clone your repo first, then retry.'
  exit 1
fi

cd '${REMOTE_DIR}'
git fetch --all --tags
git checkout '${GIT_REF}'
git pull --ff-only || true

if [[ -f scripts/init_db.py ]]; then
  python3 scripts/init_db.py
fi

sudo systemctl restart '${SERVICE_NAME}'
sudo systemctl is-active '${SERVICE_NAME}'
echo '[deploy] done'
"

