#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/rollback_remote.sh <ssh_host> <git_ref_or_tag>
# Example:
#   ./scripts/rollback_remote.sh ubuntu@ops-server v2026.04.25

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <ssh_host> <git_ref_or_tag>"
  exit 1
fi

SSH_HOST="$1"
ROLLBACK_REF="$2"
REMOTE_DIR="${REMOTE_DIR:-/srv/swap-ops-dashboard}"
SERVICE_NAME="${SERVICE_NAME:-swap-ops.service}"

echo "[rollback] host=${SSH_HOST} ref=${ROLLBACK_REF} dir=${REMOTE_DIR} service=${SERVICE_NAME}"

ssh "${SSH_HOST}" "set -euo pipefail
cd '${REMOTE_DIR}'
git fetch --all --tags
git checkout '${ROLLBACK_REF}'

if [[ -f scripts/init_db.py ]]; then
  python3 scripts/init_db.py
fi

sudo systemctl restart '${SERVICE_NAME}'
sudo systemctl is-active '${SERVICE_NAME}'
echo '[rollback] done'
"

