#!/bin/bash
# Delegator worktree cleanup cron script
# Run: crontab -e -> 0 * * * * /path/to/cleanup.sh /path/to/project [ttl_hours]

PROJECT="${1:-.}"
TTL="${2:-24}"

find "${PROJECT}/.delegation/worktrees" -maxdepth 1 -type d -mmin +$((TTL * 60)) -exec rm -rf {} \; 2>/dev/null
git -C "$PROJECT" worktree prune 2>/dev/null
echo "$(date): Cleaned worktrees (TTL: ${TTL}h) in $PROJECT"
