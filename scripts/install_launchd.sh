#!/bin/bash
set -euo pipefail

PROJECT_DIR="${SNS_AUTOMATIC_PROJECT_DIR:-$HOME/Documents/SNS_Automatic_System}"
PLIST_NAME="com.seongjegeun.sns-automatic.run-cycle.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
chmod +x run_cycle.sh

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.seongjegeun.sns-automatic.run-cycle</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$PROJECT_DIR/run_cycle.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>

  <key>StartInterval</key>
  <integer>10800</integer>

  <key>RunAtLoad</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/launchd.out.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/launchd.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/com.seongjegeun.sns-automatic.run-cycle"

cat <<EOF
✅ launchd registration complete.

Plist: $PLIST_PATH
Project: $PROJECT_DIR
Interval: 10800 seconds, every 3 hours
Logs:
- $LOG_DIR/run_cycle.log
- $LOG_DIR/launchd.out.log
- $LOG_DIR/launchd.err.log

Check status:
launchctl print gui/$(id -u)/com.seongjegeun.sns-automatic.run-cycle

Run manually:
cd "$PROJECT_DIR" && ./run_cycle.sh

Uninstall:
launchctl bootout gui/$(id -u) "$PLIST_PATH"
rm -f "$PLIST_PATH"
EOF
