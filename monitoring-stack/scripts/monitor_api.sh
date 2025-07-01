#!/usr/bin/bash

# this script needs A set of files and directory structure.
#.
#└── monitoring-stack
#    ├── .env
#    ├── postman_collection
#    │   ├── fail_postman_collections.json
#    │   ├── postman_collections.json
#    │   └── postman_environment.json
#    └── scripts
#        └── monitor-api.sh
#


# Load environment variables
source "/home/ubuntu/monitoring-stack/.env"

# Timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Directories
#SCRIPT_DIR=$(dirname "$0")
#LOG_DIR="/var/log/postman_logs"
#OUTPUT_FILE="$LOG_DIR/output.json"

# Directories
SCRIPT_DIR="."
LOG_DIR="/var/log/postman_logs"

# This test is to see if there is an argument with the command to evoke the test .json
if [[ $# -ge 1 ]]; then
  COLLECTION="/home/ubuntu/monitoring-stack/postman_collection/fail_postman_collections.json"
else 
  COLLECTION="/home/ubuntu/monitoring-stack/postman_collection/postman_collections.json"
fi

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

  REQUEST_BODY=$(echo "$EXECUTION" | jq -r '.request.body.raw // .request.body.graphql.query // "No request body found"')
  RESPONSE_BODY=$(echo "$EXECUTION" | jq -r '
    if .response.body then
      .response.body
    elif .response.stream.data then
      (.response.stream.data | map(tonumber) | implode)
    else
      "No response body found"
    end
  ')

  HTTP_STATUS=$(echo "$EXECUTION" | jq -r '.response.code // "No status code"')
  RESPONSE_HEADERS=$(echo "$EXECUTION" | jq -r '.response.headers // [] | map("\(.key): \(.value)") | join("\n")')
  HEADERS_DISPLAY="${RESPONSE_HEADERS:-No headers received}"

  REQUEST_URL=$(echo "$EXECUTION" | jq -r '.request.url.raw // .request.url // "unknown"')
  RESPONSE_SIZE=$(echo "$EXECUTION" | jq -r '.response.responseSize // "?"')
  RESPONSE_TIME=$(echo "$EXECUTION" | jq -r '.response.responseTime // "?"')
  RESPONSE_MIME=$(echo "$EXECUTION" | jq -r '.response.mimeType // "?"')
  UPLOAD_SIZE="${RESPONSE_SIZE}B↑"
  DOWNLOAD_SIZE="${RESPONSE_SIZE}B↓"  # If not available separately, reuse total size

  # 🔧 Truncate long fields
  TRIMMED_REQUEST=$(echo "$REQUEST_BODY" | head -c 1000)
  TRIMMED_RESPONSE=$(echo "$RESPONSE_BODY" | head -c 1000)
  TRIMMED_ERROR=$(echo "$ERROR_MESSAGE" | head -c 500)

  # ✅ Formatted message
  MESSAGE="⚠🔥Something is down🔥⚠

  queryName: $QUERY_NAME
  timestamp: $TIMESTAMP
  request: $TRIMMED_REQUEST

  → $QUERY_NAME
  POST $REQUEST_URL
  $HTTP_STATUS OK ★ ${RESPONSE_TIME}ms time ★ $UPLOAD_SIZE $DOWNLOAD_SIZE size ★ $RESPONSE_MIME

  headers: $HEADERS_DISPLAY
  response: $TRIMMED_RESPONSE
  error: $TRIMMED_ERROR"

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="$TELEGRAM_CHAT_ID" \
      -d text="$MESSAGE"
fi