#!/bin/sh
# Installs the superwhisper-optimize skill.
# Claude Code (default):  curl -fsSL <this file's raw URL> | sh
# Codex:                  curl -fsSL <this file's raw URL> | sh -s -- --codex
set -e
BASE="https://raw.githubusercontent.com/superultrainc/superwhisper-docs/main/skills/superwhisper-optimize"
DIR="$HOME/.claude/skills/superwhisper-optimize"
[ "$1" = "--codex" ] && DIR="$HOME/.codex/skills/superwhisper-optimize"
mkdir -p "$DIR/references"
curl -fsSL -o "$DIR/SKILL.md" "$BASE/SKILL.md"
curl -fsSL -o "$DIR/references/mode-schema.md" "$BASE/references/mode-schema.md"
echo "Installed superwhisper-optimize to $DIR"
echo "Start a new agent session and run /superwhisper-optimize"
