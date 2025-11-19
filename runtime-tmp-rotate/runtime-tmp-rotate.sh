#!/usr/bin/env bash
# Cleanup old temporary media files (>24h)
# Safe to run multiple times (idempotent)

BASE_DIR="/var/www/peer_beta/peer_backend/runtime-data"
TMP_DIR="$BASE_DIR/media/tmp"
LOG_DIR="$BASE_DIR/logs/cron-workers/upload-post-tmp-files-cleanup"
DATE_TAG="$(date +'%Y-%m-%d-%H%M')"
LOG_FILE="$LOG_DIR/${DATE_TAG}-upload-post-tmp-files-cleanup.log"

# make a directory if not there already
if [[ ! -d $LOG_DIR ]]; then
    mkdir -p "$LOG_DIR"
    touch "$LOG_FILE"
else
    touch "$LOG_FILE"
fi


echo "*** [$(date '+%Y-%m-%d %H:%M:%S')] Starting cleanup... ***" >> "$LOG_FILE" 
echo "Finding files from $TMP_DIR"
#
FIND_COUNT=$(find "$TMP_DIR" -type f -mmin +1440 -print | wc -l)
#
echo "Found $FIND_COUND files older then required"

# Check for dry-run mode
if [[ "$1" == "--delete" ]]; then
    echo "[INFO] Running in delete mode" >> "$LOG_FILE"
    FIND_CMD=(find "$TMP_DIR" -type f -mmin +1440 -print -delete)
    EFFECT=DELETED_FILES
else
    echo "[INFO] Running in dry-run mode (no files will be deleted)" >> "$LOG_FILE"
    FIND_CMD=(find "$TMP_DIR" -type f -mmin +1440 -print)
    EFFECT=FIND_ONLY
fi


echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleanup finished." >> "$LOG_FILE"
echo "$EFFECT :-------------------------------------" >> "$LOG_FILE"
