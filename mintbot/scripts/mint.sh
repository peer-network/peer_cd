#!/bin/bash

### test push to see deployment.
### set


set -euo pipefail

# Load environment variables
source /home/ubuntu/peer_cd/mintbot/.env

# Timestamped log directory
TS=$(date +"%Y%m%d%H%M%S")
LOGDIR="$path_to_logs_root_dir/mint_$TS"
LOGFILE="$LOGDIR/log_file.txt"

# Telegram functions
notify_error() {
    curl -s -X POST "https://api.telegram.org/bot$TG_bot_API_key/sendMessage" \
        -d chat_id="$TG_chat_id" \
        -d parse_mode="Markdown" \
        -d text="*Failed to mint* on \`$endpoint\`\nSee logs: \`$LOGDIR\`"
}

notify_success() {
    curl -s -X POST "https://api.telegram.org/bot$TG_bot_API_key/sendMessage" \
        -d chat_id="$TG_chat_id" \
        -d parse_mode="Markdown" \
        -d disable_notification=true \
        -d text="*Successfully minted* on \`$endpoint\`"
}

log_info() {
    echo "[INFO] [$(date '+%Y-%m-%d %H:%M:%S')]: $1" | tee -a "$LOGFILE"
}

log_error() {
    echo "[ERROR] [$(date '+%Y-%m-%d %H:%M:%S')]: $1" | tee -a "$LOGFILE"
}

# Setup log directory
mkdir -p "$LOGDIR"
touch "$LOGFILE"

# Load secrets
email=$(cat /home/ubuntu/peer_cd/mintbot/secrets/email.txt)
pass=$(cat /home/ubuntu/peer_cd/mintbot/secrets/pass.txt)
TG_bot_API_key=$(cat /home/ubuntu/peer_cd/mintbot/secrets/tg_bot_api_key.txt)

# Perform login mutation
login_query=$(cat <<EOF
mutation {
  login(email: "$email", password: "$pass") {
    status
    ResponseCode
    accessToken
  }
}
EOF
)

LOGIN_RES=$(curl -s -X POST "$endpoint" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$login_query\"}")

echo "$LOGIN_RES" > "$LOGDIR/login_response.txt"

accessToken=$(echo "$LOGIN_RES" | jq -r '.data.login.accessToken // empty')
loginStatus=$(echo "$LOGIN_RES" | jq -r '.data.login.status // empty')

if [[ "$loginStatus" != "success" || -z "$accessToken" ]]; then
    log_error "Login failed"
    notify_error
    exit 1
else
    log_info "Login successful"
fi

AUTH_HEADER="Authorization: Bearer $accessToken"

# Helper function to run GraphQL queries
run_query() {
    local name=$1
    local query=$2
    local DIR="$LOGDIR/$name"

    mkdir -p "$DIR"
    echo "$query" > "$DIR/request.txt"

    RESPONSE=$(curl -s -X POST "$endpoint" -H "Content-Type: application/json" -H "$AUTH_HEADER" \
        -d "{\"query\":\"$query\"}")
    echo "$RESPONSE" > "$DIR/response.txt"

    STATUS=$(echo "$RESPONSE" | jq -r ".data.$name.status // empty")

    if [[ "$STATUS" == "success" ]]; then
        log_info "$name: success"
    else
        log_error "$name: failed"
        notify_error
        exit 1
    fi
}

# Run all 3 minting-related queries
run_query "globalwins" "query { globalwins { status ResponseCode } }"

run_query "gemster" "query { gemster { status ResponseCode affectedRows { d0 d1 d2 d3 d4 d5 w0 m0 y0 } } }"

# Final query with custom handling
name="gemsters"
query="query { gemsters(day: D1) { status counter ResponseCode affectedRows { winStatus { totalGems gemsintoken bestatigung } userStatus { userid gems tokens percentage details { gemid userid postid fromid gems numbers whereby createdat } } } } }"
DIR="$LOGDIR/$name"

mkdir -p "$DIR"
echo "$query" > "$DIR/request.txt"

RESPONSE=$(curl -s -X POST "$endpoint" -H "Content-Type: application/json" -H "$AUTH_HEADER" \
    -d "{\"query\":\"$query\"}")
echo "$RESPONSE" > "$DIR/response.txt"

STATUS=$(echo "$RESPONSE" | jq -r ".data.$name.status // empty")

if [[ "$STATUS" == "success" ]]; then
    log_info "$name: success"
    notify_success
else
    log_error "$name: failed"
    notify_error
    exit 1
fi
