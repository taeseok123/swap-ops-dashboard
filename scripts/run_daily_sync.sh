#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

if [[ -z "${REDASH_API_KEY:-}" ]]; then
  echo "[ERROR] REDASH_API_KEY is not set" >&2
  exit 1
fi

cd "$ROOT"
python3 "$ROOT/scripts/refresh_validate_daily.py" \
  --api-key "$REDASH_API_KEY" \
  --report-dir "$ROOT/reports/validation" \
  >> "$LOG_DIR/daily_sync.log" 2>&1
