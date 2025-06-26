\#!/usr/bin/bash

# === Load environment ===
source "/home/ubuntu/monitoring-stack/.env"

# === Determine which collection to use ===
if [[ $# -ge 1 ]]; then
  COLLECTION="/home/ubuntu/monitoring-stack/postman_collection/fail_postman_collections.json"
else 
  COLLECTION="/home/ubuntu/monitoring-stack/postman_collection/postman_collections.json"
fi

# === File paths ===
ENVIRONMENT="/home/ubuntu/monitoring-stack/postman_collection/postman_environment.json"
PYTHON_PARSER="/home/ubuntu/monitoring-stack/scripts/newmanStdoutVersobeParser.py"
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
CLEANED_MESSAGE=$(grep -vEi 'output\.txt' "$OUTPUT_TXT" | grep -vE '^\s*$' \
  | sed 's/{/{\n/g' \
  | sed 's/}/}\n/g' \
  | sed 's/"/\\"/g' \
  | sed 's/^/ /')
  MAX_LENGTH=3800  # Telegram limit is 4096, keep buffer
  while IFS= read -r chunk; do
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="$TELEGRAM_CHAT_ID" \
       --data-urlencode text="$chunk"
  done < <(echo "$CLEANED_MESSAGE" | fold -w $MAX_LENGTH -s)
  echo "✅ No failed tests detected by verbose parser."
fi
