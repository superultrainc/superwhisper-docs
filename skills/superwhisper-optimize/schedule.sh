#!/bin/sh
# Schedules a weekly Superwhisper optimization run (Mondays 9:00) via launchd.
#   Claude Code (default): curl -fsSL <this file's raw URL> | sh
#   Codex:                 curl -fsSL <this file's raw URL> | sh -s -- --codex
#   Remove the schedule:   curl -fsSL <this file's raw URL> | sh -s -- --remove
set -e
LABEL="com.superwhisper.optimize-weekly"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/superwhisper-optimize.log"
PROMPT="Run the superwhisper-optimize skill non-interactively: fresh pass over my latest history, sensible defaults, additive changes only."

if [ "$1" = "--remove" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed the weekly optimization schedule."
  exit 0
fi

# Locate the active Superwhisper folder; the agent runs with this as its
# working directory so its sandbox covers the files it needs to change.
PARENT=$(defaults read com.superduper.superwhisper appFolderDirectory 2>/dev/null || true)
if [ -n "$PARENT" ] && [ -d "$PARENT/superwhisper/modes" ]; then
  SW_DIR="$PARENT/superwhisper"
elif [ -d "$HOME/Documents/superwhisper/modes" ]; then
  SW_DIR="$HOME/Documents/superwhisper"
elif [ -d "$HOME/superwhisper/modes" ]; then
  SW_DIR="$HOME/superwhisper"
else
  echo "Could not find your Superwhisper folder (no modes/ directory)." >&2
  echo "Open Settings -> Configuration -> Advanced to see its location, then run this script from that folder." >&2
  exit 1
fi

CMD="cd '$SW_DIR' && claude -p \"$PROMPT\" --allowedTools \"Skill,Bash,Read,Write,Edit\""
[ "$1" = "--codex" ] && CMD="codex exec -C '$SW_DIR' -s workspace-write --skip-git-repo-check \"$PROMPT\""

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>$CMD >> $LOG 2>&amp;1</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>1</integer>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
</dict>
</plist>
PLIST_EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Scheduled weekly optimization (Mondays 9:00)."
echo "Superwhisper folder: $SW_DIR"
echo "Log: $LOG"
echo "Remove later with: sh schedule.sh --remove"
