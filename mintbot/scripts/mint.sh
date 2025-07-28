#!/bin/bash

### test push to see deployment.
### merge good


set -euo pipefail

# Load environment variables
source /home/ubuntu/peer_cd/mintbot/.env

# Timestamped log directory
TS=$(date +"%Y%m%d%H%M%S")
LOGDIR="$path_to_logs_root_dir/mint_$TS"
LOGFILE="$LOGDIR/log_file.txt"

# Telegram functions
notify_error() {
    # Response files
    local login_res="$LOGDIR/login_response.txt"
    local globalwins_res="$LOGDIR/globalwins/response.txt"
    local gemster_res="$LOGDIR/gemster/response.txt"
    local gemsters_res="$LOGDIR/gemsters/response.txt"

    # Preview first 500 chars of each
    local login_preview=$(head -c 500 "$login_res" 2>/dev/null)
    local globalwins_preview=$(head -c 500 "$globalwins_res" 2>/dev/null)
    local gemster_preview=$(head -c 500 "$gemster_res" 2>/dev/null)
    local gemsters_preview=$(head -c 500 "$gemsters_res" 2>/dev/null)

    local msg="*Minting Failed* on \`$endpoint\`

*Login Response:*
\`\`\`
$login_preview
\`\`\`

*globalwins Response:*
\`\`\`
$globalwins_preview
\`\`\`

*gemster Response:*
\`\`\`
$gemster_preview
\`\`\`

*gemsters Response:*
\`\`\`
$gemsters_preview
\`\`\`

See full logs: \`$LOGDIR\`"

    curl -s -X POST "https://api.telegram.org/bot$TG_bot_API_key/sendMessage" \
        -d chat_id="$TG_chat_id" \
        -d parse_mode="Markdown" \
        --data-urlencode "text=$msg"
}

notify_success() {
    curl -s -X POST "https://api.telegram.org/bot$TG_bot_API_key/sendMessage" \
        -d chat_id="$TG_chat_id" \
        -d parse_mode="Markdown" \
        -d disable_notification=true \
        -d text="*Successfully minted* on \`$endpoint\`"
}

notify_warning() {
    local name="$1"

    local res_path="$LOGDIR/$name/response.txt"
    local preview=$(head -c 500 "$res_path" 2>/dev/null)

    local msg="*Warning*: \`$name\` returned success but no activity on \`$endpoint\`

*Response:*
\`\`\`
$preview
\`\`\`

See full logs: \`$LOGDIR\`"

    curl -s -X POST "https://api.telegram.org/bot$TG_bot_API_key/sendMessage" \
        -d chat_id="$TG_chat_id" \
        -d parse_mode="Markdown" \
        --data-urlencode "text=$msg"
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

LOGIN_RES=$(jq -n --arg q "$login_query" '{query: $q}' | \
  curl -s -X POST "$endpoint" \
       -H "Content-Type: application/json" \
       -d @-)

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

    RESPONSE=$(jq -n --arg q "$query" '{query: $q}' | \
      curl -s -X POST "$endpoint" -H "Content-Type: application/json" -H "$AUTH_HEADER" \
           -d @-)

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
# Run globalwins with custom check
name="globalwins"
query="query { globalwins { status ResponseCode } }"
DIR="$LOGDIR/$name"

mkdir -p "$DIR"
echo "$query" > "$DIR/request.txt"

RESPONSE=$(jq -n --arg q "$query" '{query: $q}' | \
  curl -s -X POST "$endpoint" -H "Content-Type: application/json" -H "$AUTH_HEADER" -d @-)

echo "$RESPONSE" > "$DIR/response.txt"

STATUS=$(echo "$RESPONSE" | jq -r ".data.$name.status // empty")
RESPONSE_CODE=$(echo "$RESPONSE" | jq -r ".data.$name.ResponseCode // empty")

if [[ "$STATUS" == "success" ]]; then
    if [[ "$RESPONSE_CODE" =~ ^2 ]]; then
        log_info "$name: success but no activity (ResponseCode $RESPONSE_CODE)"
        notify_warning "$name"
    else
        log_info "$name: success"
    fi
else
    log_error "$name: failed"
    notify_error
    exit 1
fi

run_query "gemster" "query { gemster { status ResponseCode affectedRows { d0 d1 d2 d3 d4 d5 w0 m0 y0 } } }"

# Final query with custom handling
# Final query: gemsters with custom check
name="gemsters"
query="query { gemsters(day: D1) { status counter ResponseCode affectedRows { winStatus { totalGems gemsintoken bestatigung } userStatus { userid gems tokens percentage details { gemid userid postid fromid gems numbers whereby createdat } } } } }"
DIR="$LOGDIR/$name"

mkdir -p "$DIR"
echo "$query" > "$DIR/request.txt"

RESPONSE=$(jq -n --arg q "$query" '{query: $q}' | \
  curl -s -X POST "$endpoint" -H "Content-Type: application/json" -H "$AUTH_HEADER" -d @-)

echo "$RESPONSE" > "$DIR/response.txt"

STATUS=$(echo "$RESPONSE" | jq -r ".data.$name.status // empty")
RESPONSE_CODE=$(echo "$RESPONSE" | jq -r ".data.$name.ResponseCode // empty")

if [[ "$STATUS" == "success" ]]; then
    if [[ "$RESPONSE_CODE" =~ ^2 ]]; then
        log_info "$name: success but no activity (ResponseCode $RESPONSE_CODE)"
        notify_warning "$name"
    else
        log_info "$name: success"
        notify_success
    fi
else
    log_error "$name: failed"
    notify_error
    exit 1
fi