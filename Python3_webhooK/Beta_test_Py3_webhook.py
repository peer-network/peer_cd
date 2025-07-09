import os
import hmac
import hashlib
import subprocess
from flask import Flask, request, abort

app = Flask(__name__)

# Read the GitHub webhook secret from environment variable
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").encode()

# Your target GitHub repo
TARGET_REPO = "peer-network/peer_cd"

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

@app.route('/github-webhook', methods=['POST'])
def github_webhook():
    payload = request.data
    sig_header = request.headers.get('X-Hub-Signature-256', '')

    if not verify_signature(payload, sig_header):
        abort(403, 'Signature verification failed')

    data = request.get_json()
    if not data or 'repository' not in data:
        abort(400, 'Missing repository data')

    repo_full_name = data['repository'].get('full_name', '')
    if repo_full_name != TARGET_REPO:
        abort(400, f'Ignored repo: {repo_full_name}')

    # Run your rsync sync script
    subprocess.Popen(["/home/ubuntu/sync_to_group.sh"])

    return 'Webhook received and processed', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
