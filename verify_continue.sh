#!/bin/bash
set -e

SESSION_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')

echo "Using session: $SESSION_ID"
echo ""

echo "=== Turn 1: Setting memory ==="
echo "Remember: my favorite color is blue" | claude --print --output-format text --session-id "$SESSION_ID" --fork-session
echo ""

echo "=== Turn 2: Recall WITH --continue ==="
echo "What's my favorite color?" | claude --print --output-format text --session-id "$SESSION_ID" --continue
