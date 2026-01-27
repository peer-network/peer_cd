#!/usr/bin/bash

set -euo pipefail

# Load environment variables
source "/home/ubuntu/monitoring-stack/.env"

REDIS_HOST=${REDIS_HOST:-127.0.0.1}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD=${REDIS_PASSWORD:-}
QUEUE_LENGTH_KEY=${QUEUE_LENGTH_KEY:-}
QUEUE_LENGTH_MAX=${QUEUE_LENGTH_MAX:-1000}
WORKER_HEARTBEAT_KEY=${WORKER_HEARTBEAT_KEY:-}
WORKER_HEARTBEAT_MAX_AGE=${WORKER_HEARTBEAT_MAX_AGE:-120}
WORKER_ERROR_KEY=${WORKER_ERROR_KEY:-}

LOG_DIR="/var/log/redis_monitor"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="$LOG_DIR/redis_monitor.log"

REDIS_CLI=(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT")
if [[ -n "$REDIS_PASSWORD" ]]; then
  REDIS_CLI+=( -a "$REDIS_PASSWORD" )
fi

log_info() {
  echo "[INFO] [$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log_error() {
  echo "[ERROR] [$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

send_telegram_alert() {
  local message="$1"
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="$message" >/dev/null
}

alert_messages=()

PING_RESULT=$(${REDIS_CLI[@]} ping 2>&1 || true)
if [[ "$PING_RESULT" != "PONG" ]]; then
  alert_messages+=("Redis PING failed: $PING_RESULT")
  log_error "Redis PING failed: $PING_RESULT"
else
  log_info "Redis PING ok"
fi

REDIS_INFO=$(${REDIS_CLI[@]} info 2>&1 || true)
if [[ "$REDIS_INFO" == *"ERR"* || -z "$REDIS_INFO" ]]; then
  alert_messages+=("Redis INFO failed: ${REDIS_INFO:-no output}")
  log_error "Redis INFO failed"
else
  echo "$REDIS_INFO" > "$LOG_DIR/redis_info.txt"
  log_info "Redis INFO captured"
fi

if [[ -n "$QUEUE_LENGTH_KEY" ]]; then
  QUEUE_LENGTH=$(${REDIS_CLI[@]} llen "$QUEUE_LENGTH_KEY" 2>&1 || true)
  if [[ "$QUEUE_LENGTH" =~ ^[0-9]+$ ]]; then
    log_info "Queue $QUEUE_LENGTH_KEY length: $QUEUE_LENGTH"
    if (( QUEUE_LENGTH > QUEUE_LENGTH_MAX )); then
      alert_messages+=("Queue $QUEUE_LENGTH_KEY length $QUEUE_LENGTH exceeds $QUEUE_LENGTH_MAX")
    fi
  else
    alert_messages+=("Queue length check failed for $QUEUE_LENGTH_KEY: $QUEUE_LENGTH")
  fi
fi

if [[ -n "$WORKER_HEARTBEAT_KEY" ]]; then
  HEARTBEAT_VALUE=$(${REDIS_CLI[@]} get "$WORKER_HEARTBEAT_KEY" 2>&1 || true)
  if [[ "$HEARTBEAT_VALUE" =~ ^[0-9]+$ ]]; then
    NOW_EPOCH=$(date +%s)
    AGE=$(( NOW_EPOCH - HEARTBEAT_VALUE ))
    log_info "Worker heartbeat age: ${AGE}s"
    if (( AGE > WORKER_HEARTBEAT_MAX_AGE )); then
      alert_messages+=("Worker heartbeat stale (${AGE}s > ${WORKER_HEARTBEAT_MAX_AGE}s)")
    fi
  else
    alert_messages+=("Worker heartbeat missing or invalid: $HEARTBEAT_VALUE")
  fi
fi

WORKER_ERROR_MESSAGE=""
if [[ -n "$WORKER_ERROR_KEY" ]]; then
  WORKER_ERROR_MESSAGE=$(${REDIS_CLI[@]} get "$WORKER_ERROR_KEY" 2>&1 || true)
  if [[ -n "$WORKER_ERROR_MESSAGE" && "$WORKER_ERROR_MESSAGE" != "(nil)" ]]; then
    log_info "Worker error captured"
  else
    WORKER_ERROR_MESSAGE=""
  fi
fi

if (( ${#alert_messages[@]} > 0 )); then
  MESSAGE="Redis monitor alert at $TIMESTAMP\n\n"
  MESSAGE+="Host: $REDIS_HOST:$REDIS_PORT\n"
  MESSAGE+="Issues:\n- $(printf '%s\n- ' "${alert_messages[@]}")"
  if [[ -n "$WORKER_ERROR_MESSAGE" ]]; then
    MESSAGE+="\nWorker error: ${WORKER_ERROR_MESSAGE}"
  fi
  send_telegram_alert "$MESSAGE"
fi
