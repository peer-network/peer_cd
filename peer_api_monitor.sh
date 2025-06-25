#!/usr/bin/bash

# Load environment variables
source "/home/ubuntu/monitoring-stack/.env"

# Timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Directories
#SCRIPT_DIR=$(dirname "$0")
#LOG_DIR="/var/log/postman_logs"
#COLLECTION="$SCRIPT_DIR/../postman_collection/postman_collections.json"
#ENVIRONMENT="$SCRIPT_DIR/../postman_collection/postman_environment.json"
#OUTPUT_FILE="$LOG_DIR/output.json"

# Directories
SCRIPT_DIR="."
LOG_DIR="/var/log/postman_logs"
COLLECTION="/home/ubuntu/monitoring-stack/postman_collection/postman_collections.json"
ENVIRONMENT="/home/ubuntu/monitoring-stack/postman_collection/postman_environment.json"
OUTPUT_FILE="$LOG_DIR/output.json"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# time stamp at run
echo "=== Running from Monitor Time: $TIMESTAMP ==="

# Run Newman and save output
newman run "$COLLECTION" -e "$ENVIRONMENT" --reporters cli,json --reporter-json-export "$OUTPUT_FILE"

FAIL_COUNT=$(jq '.run.failures | length' "$OUTPUT_FILE")

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  QUERY_NAME=$(jq -r '.run.failures[0].source.name' "$OUTPUT_FILE")
  ERROR_MESSAGE=$(jq -r '.run.failures[0].error.message' "$OUTPUT_FILE")
  EXECUTION=$(jq --arg q "$QUERY_NAME" '.run.executions[] | select(.item.name == $q)' "$OUTPUT_FILE")
  REQUEST_BODY=$(echo "$EXECUTION" | jq -r '.request.body.raw // "No request body found"')
  RESPONSE_BODY=$(echo "$EXECUTION" | jq -r '.response.body // "No response body found"')
# 🔧 Truncate long fields to avoid "argument list too long" errors
  TRIMMED_REQUEST=$(echo "$REQUEST_BODY" | head -c 1000)
  TRIMMED_RESPONSE=$(echo "$RESPONSE_BODY" | head -c 1000)
  TRIMMED_ERROR=$(echo "$ERROR_MESSAGE" | head -c 500)


MESSAGE="⚠🔥Something is down🔥⚠️
queryName: $QUERY_NAME
timestamp: $TIMESTAMP
request: $TRIMMED_REQUEST
response: $TRIMMED_RESPONSE
error: $TRIMMED_ERROR"

  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="$MESSAGE"
fi

