#!/bin/bash

### to migrated teh main peer-network database


source /home/ubuntu/.env.deploy

if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "*** ERROR: GITHUB_TOKEN is not set. ***"
  exit 1
fi

if [[ -z "$PR_NUMBER" ]]; then
  echo "*** PR_NUMBER not set. Aborting... ***"
  exit 1
fi

REPO="peer-network/peer_backend"
PR_API_URL="https://api.github.com/repos/$REPO/pulls/$PR_NUMBER/files"

CHANGED_FILES=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$PR_API_URL" | jq -r '.[].filename')

SQL_CHANGED=false
for file in $CHANGED_FILES; do
  if [[ "$file" == sql_files_for_import/* ]]; then
    SQL_CHANGED=true
    break
  fi
done

if [[ "$SQL_CHANGED" == false ]]; then
  echo "*** No SQL files changed — skipping DB update and deploying backend only. ***
  /home/ubuntu/deploy-scripts/deploy-backend.sh >> /var/log/deploy.log 2>&1
  exit 0
fi

echo "=== SQL files changed — proceeding with DB update...==="

echo "=== DB Update Started at $(date) ==="

DB_SUCCESS=true

{ 
  set -e

  # Identify latest database

LATEST_DB=$(psql -U postgres -Atc \
  "SELECT datname FROM pg_database WHERE datname LIKE 'peer_%' ORDER BY datname DESC LIMIT 1;")

if [[ -z "$LATEST_DB" ]]; then
  echo "*** Could not detect latest DB. Proceeding with backend deployment anyway. ***"
  /home/ubuntu/deploy-scripts/deploy-backend.sh >> /var/log/deploy.log 2>&1
  exit 0
fi

if [[ "$LATEST_DB" =~ ^peer_[0-9]{4}_[0-9]{2}_[0-9]{2}_[0-9]+$ ]]; then
  echo "*** Latest DB detected: $LATEST_DB ***"
else
  echo "*** Latest DB does not include PR number — Failing ***"
  exit 1
fi

# Define today's date
TODAY=$(date +%Y_%m_%d)

# Check for PR_NUMBER
if [[ -z "$PR_NUMBER" ]]; then
  echo "*** PR_NUMBER not set. Aborting DB creation."
  exit 1
else
  echo "=== PR_NUMBER found: $PR_NUMBER"
fi

NEW_DB="peer_${TODAY}_${PR_NUMBER}"


if psql -U postgres -lqt | cut -d \| -f 1 | grep -qw "$NEW_DB"; then
  echo "No new DB needed ($NEW_DB already exists) — proceeding to backend deployment."
  /home/ubuntu/deploy-scripts/deploy-backend.sh >> /var/log/deploy.log 2>&1
  exit 0
fi

echo "=== Creating new DB: $NEW_DB"

# Clone DB (requires pg_dump & createdb)
createdb -U postgres "$NEW_DB"
pg_dump -U postgres "$LATEST_DB" | psql -U postgres "$NEW_DB"

# Applying Changes in sql_files_for_import to the New cloned DB
echo "== Applying updated structure.psql and additional_data.sql to $NEW_DB =="
STRUCTURE_PSQL1="/var/www/peer_beta/peer_backend/sql_files_for_import/structure.psql"
ADDITIONAL_SQL1="/var/www/peer_beta/peer_backend/sql_files_for_import/additional_data.sql"

if [[ -f "$STRUCTURE_PSQL1" ]]; then
  echo "Applying $STRUCTURE_PSQL1"
  psql -U postgres -d "$NEW_DB" -f "$STRUCTURE_PSQL1"
else
  echo "STRUCTURE_PSQL1 file not found, skipping $STRUCTURE_PSQL1"
fi

if [[ -f "$ADDITIONAL_SQL1" ]]; then
  echo "Applying $ADDITIONAL_SQL1"
  psql -U postgres -d "$NEW_DB" -f "$ADDITIONAL_SQL1"
else
  echo "Data file not found, skipping $ADDITIONAL_SQL1"
fi

echo "DB $NEW_DB ready with latest structure"

echo "$NEW_DB" > /tmp/active_db.txt

echo "=== Starting backend deployment ==="
/home/ubuntu/deploy-scripts/deploy-backend.sh >> /var/log/deploy.log 2>&1
exit 0

} || {
  echo "*** DB update failed — backend will NOT deploy ***"
  exit 1
}


ssh -L 63333:db.foo.com:5432 joe@shell.foo.com