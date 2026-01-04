#!/bin/bash

SESSION_ID="test-session-$(uuidgen)"

echo "=== Test 1: Setting name ==="
echo "My name is Alice" | claude --print --output-format stream-json --verbose --session-id "$SESSION_ID" 2>&1 | grep '"type":"assistant"' | jq -r '.message.content[0].text'

echo ""
echo "=== Test 2: Recall WITHOUT --continue ==="
echo "What's my name?" | claude --print --output-format stream-json --verbose --session-id "$SESSION_ID" 2>&1 | grep '"type":"assistant"' | jq -r '.message.content[0].text'

echo ""
echo "=== Test 3: Recall WITH --continue ==="
echo "What's my name?" | claude --print --output-format stream-json --verbose --session-id "$SESSION_ID" --continue 2>&1 | grep '"type":"assistant"' | jq -r '.message.content[0].text'
