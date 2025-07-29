#!/bin/bash

#  This cleans up the logs for mintbot.
#  All logs over 100 or over 14 days old are purged.


LOG_DIR="/home/ubuntu/peer_cd/mintbot/logs"
EVENT_LOG="/var/log/mintlog/mint.log"

# 1. Remove logs older than 14 days
find "$LOG_DIR" -type d -mtime +14 -exec rm -rf {} +

# 2. Keep only the newest 100 directories
ls -1dt "$LOG_DIR"/* 2>/dev/null | tail -n +101 | xargs -d '\n' rm -rf --

# --- Curtail mint log file if larger than 200K ---
if [ -f "$EVENT_LOG" ]; then
    size=$(stat -c%s "$EVENT_LOG")
    if [ "$size" -gt "$MAX_SIZE" ]; then
        echo "[$(date)] Trimming $EVENT_LOG (size=$size)"
        # Keep last 1000 lines (adjust if needed)
        tail -n 1000 "$EVENT_LOG" > "${EVENT_LOG}.tmp" && mv "${EVENT_LOG}.tmp" "$EVENT_LOG"
    fi
fi