#!/bin/bash

# Test Claude Code CLI session persistence

SESSION_ID="voice-test-$(uuidgen)"

echo "=== Test 1: Remember number ==="
echo "Remember this number: 42" | claude --print --output-format stream-json --verbose --session-id "$SESSION_ID" 2>/dev/null | grep '"type":"assistant"' | jq -r '.message.content[0].text'

echo ""
echo "=== Test 2: Recall number (same session) ==="
echo "What number did I tell you to remember?" | claude --print --output-format stream-json --verbose --session-id "$SESSION_ID" --continue 2>/dev/null | grep '"type":"assistant"' | jq -r '.message.content[0].text'
