#!/bin/zsh
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <REDASH_API_KEY> [HOUR] [MINUTE]"
  exit 1
fi

API_KEY="$1"
HOUR="${2:-9}"
MINUTE="${3:-5}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.swap.ops.dashboard.daily.plist"

mkdir -p "$PLIST_DIR"
mkdir -p "$ROOT/logs"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.swap.ops.dashboard.daily</string>

  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$ROOT/scripts/refresh_validate_daily.py</string>
    <string>--api-key</string>
    <string>$API_KEY</string>
    <string>--report-dir</string>
    <string>$ROOT/reports/validation</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$ROOT</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$HOUR</integer>
    <key>Minute</key>
    <integer>$MINUTE</integer>
  </dict>

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$ROOT/logs/launchd_daily_sync.out.log</string>
  <key>StandardErrorPath</key>
  <string>$ROOT/logs/launchd_daily_sync.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Installed: $PLIST_PATH"
echo "Schedule: daily ${HOUR}:${MINUTE}"
launchctl list | grep com.swap.ops.dashboard.daily || true
