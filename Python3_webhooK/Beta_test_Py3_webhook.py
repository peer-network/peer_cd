## Python 3
## webhook for github repo /peer-network/peer_cd
## To listen for git pushs to peer_cd
## Then rync to the other servers 
##

import os
import hmac
import hashlib
import subprocess
from flask import Flask, request, abort
import json
from datetime import datetime

app = Flask(__name__)

# Read the GitHub webhook secret from environment variable
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").encode()

# Your target GitHub repo
TARGET_REPO = "peer-network/peer_cd"
TARGET_BRANCH = "refs/heads/dev"

## save the log adding a timestamp to test the what is being added
def log_event(msg):
    """=== Append to webhook.log ==="""
    with open(os.path.join(LOG_DIR, "webhook.log"), "a") as log_file:
        log_file.write(f"{datetime.utcnow().isoformat()}Z {msg}\n")


## get all of the data from github, adding the timestamp
def save_raw_payload(data):
    """=== Save JSON payload to disk ==="""
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(EVENT_DIR, f"push-{ts}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path



def verify_signature(payload, sig_header):
    if not sig_header:
        return False
    try:
        sha_name, signature = sig_header.split('=')
        if sha_name != 'sha256':
            return False
        mac = hmac.new(WEBHOOK_SECRET, msg=payload, digestmod=hashlib.sha256)
        return hmac.compare_digest(mac.hexdigest(), signature)
    except Exception:
        return False

### To set the needed paths fot the webhook
@app.route('/github-webhook', methods=['POST'])
def github_webhook():
    payload = request.data
    sig_header = request.headers.get('X-Hub-Signature-256', '')

    if not verify_signature(payload, sig_header):
        abort(403, ' *** Signature verification failed ***')

    data = request.get_json()
    if not data or 'repository' not in data:
        abort(400, '*** Missing repository data ***')

    repo_full_name = data['repository'].get('full_name', '')
    if repo_full_name != TARGET_REPO:
        abort(400, f'*** Ignored repo: {repo_full_name} ***')

    branch_ref = data.get('ref', '')
    if branch_ref != TARGET_BRANCH:
        log_event(f"*** Ignored branch: {branch_ref} ***")
        return 'Branch not tracked, ignoring.', 200

    json_path = save_raw_payload(data)
    log_event(f"=== Payload saved: {json_path} ===")


    # Trigger your sync logic (you’ll refine this next)
    subprocess.Popen(["/home/ubuntu/sync_to_group.sh", json_path])

    return 'Webhook received and processed', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
