#!/usr/bin/bash

# === Load environment ===
source "/home/ubuntu/peer_cd/monitoring-stack/.env"

# === Determine which collection to use ===
if [[ $# -ge 1 ]]; then
  COLLECTION="/home/ubuntu/peer_cd/monitoring-stack/postman_collection/fail_postman_collections.json"
else 
  COLLECTION="/home/ubuntu/peer_cd/monitoring-stack/postman_collection/postman_collections.json"
fi

# === File paths ===
ENVIRONMENT="/home/ubuntu/peer_cd/monitoring-stack/postman_collection/postman_environment.json"
PYTHON_PARSER="/home/ubuntu/peer_cd/monitoring-stack/scripts/newmanStdoutVersobeParser.py"
INPUT_TXT="/var/log/postman_logs/input.txt"
OUTPUT_TXT="/var/log/postman_logs/output.txt"

# === Clear old logs ===
rm -f "$INPUT_TXT" "$OUTPUT_TXT"

# === Run Newman with verbose output ===
newman run "$COLLECTION" -e "$ENVIRONMENT" \
  --reporters cli --reporter-cli-no-success-assertions --verbose \
  > "$INPUT_TXT" 2>&1

# === Parse verbose output ===
python3 "$PYTHON_PARSER" "$INPUT_TXT" "$OUTPUT_TXT"

# === If OUTPUT has content, send to Telegram ===
if [[ -s "$OUTPUT_TXT" ]]; then
  CLEANED_FILE="/tmp/cleaned_output.txt"

  PERL5DB="" perl -CSD -i -pe 's/[\x{180E}\x{200B}\x{200C}\x{200D}\x{FEFF}]//g' "$OUTPUT_TXT"

  QUERY_NAME=$(grep -m 1 -Eo '→ .+' "$OUTPUT_TXT" | sed 's/→ //')
  # RAW_QUERY=$(awk '/┌ ↑ .*raphql/,/└/' "$OUTPUT_TXT" | grep -v '┌\|└\|↑\|↓' | sed 's/^│ //')
  RAW_QUERY=$(jq -r --arg name "$QUERY_NAME" \
    '.item[] | select(.name == $name) | .request.body.graphql.query' \
    "$COLLECTION")
  RESPONSE_BODY=$(awk '/┌ ↓ .*json/,/└/' "$OUTPUT_TXT" | grep -v '┌\|└\|↑\|↓' | sed 's/^│ //')
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

  {
    echo "=== Query Name ==="
    echo "${QUERY_NAME:-Unknown}"
    echo
    echo "=== Raw Query ==="
    echo "${RAW_QUERY:-[Not found]}"
    echo
    echo "=== Response ==="
    echo "${RESPONSE_BODY:-[Not found]}"
  } > "$CLEANED_FILE"

# === Escape MarkdownV2 special characters ===
escape_markdown() {
    printf '%s' "$1" | sed -e 's/[_*\[\]()~`>#+\-=|{}.!\\]/\\&/g'
  }

  SAFE_QUERY_NAME=$(escape_markdown "$QUERY_NAME")
  SAFE_TIMESTAMP=$(escape_markdown "$TIMESTAMP")

  # === Caption for Telegram message ===
  SUMMARY="⚠🔥 *Something is down* 🔥⚠

  *Query Name:* \`$SAFE_QUERY_NAME\`
  *Timestamp:* \`$SAFE_TIMESTAMP\`

  See attached file for more details\\."

  # === Optional debug preview ===
  echo "==== FINAL TELEGRAM CAPTION ===="
  echo "$SUMMARY"
  echo "================================"

  # === Send file + caption to Telegram ===
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendDocument" \
  -F chat_id="$TELEGRAM_CHAT_ID" \
  -F document=@"$CLEANED_FILE" \
  -F "caption=$SUMMARY" \
  -F parse_mode="MarkdownV2"

else
  echo "No failed tests detected by verbose parser."
fi