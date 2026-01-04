#!/bin/bash

SESSION_ID="memory-test-$(uuidgen)"

echo "=== Turn 1: Tell Claude your name ==="
RESULT1=$(echo "Remember: my name is Alice" | claude --print --output-format text --session-id "$SESSION_ID" 2>&1)
echo "$RESULT1"

echo ""
echo "=== Turn 2: WITHOUT --continue (should forget) ==="
RESULT2=$(echo "What is my name?" | claude --print --output-format text --session-id "$SESSION_ID" 2>&1)
echo "$RESULT2"

echo ""
echo "=== Turn 3: WITH --continue (should remember) ==="
RESULT3=$(echo "What is my name?" | claude --print --output-format text --session-id "$SESSION_ID" --continue 2>&1)
echo "$RESULT3"
