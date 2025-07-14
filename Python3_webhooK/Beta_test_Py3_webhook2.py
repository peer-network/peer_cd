#!/usr/bin/env python3
"""
GitHub Webhook Server for Jump Host Deployment
Handles GitHub push events and deploys to target servers via rsync/ssh
"""

import os
import json
import hmac
import hashlib
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime
from flask import Flask, request, jsonify
from pathlib import Path

# Read the GitHub webhook secret from environment variable
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").encode("utf-8")

# Read GitHub token from environment variable
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Your target GitHub repo
TARGET_REPO = "peer-network/peer_cd"

# Push to dev will trigger web-hook.
TARGET_BRANCH = "refs/heads/dev"

# Local deployment directory - where we'll keep the synced code
LOCAL_DEPLOY_DIR = "/opt/application/"

# Configuration
LOG_DIR = '/var/log/webhook/'
PROCESSING_DIR = '/var/log/webhook/events/'
REPO_CLONE_DIR = '/tmp/peer_cd/'

# Target servers configuration (for future rsync deployment)
TARGET_SERVERS = {
    'monitor': {
        'ip': '172.16.0.20',
        'hostname': 'monitor',
        'deploy_path': '/opt/application/',
        'user': 'deploy'
    }
}

# Setup logging
def setup_logging():
    """Setup logging configuration"""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(PROCESSING_DIR, exist_ok=True)
    
    log_file = os.path.join(LOG_DIR, 'webhook.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

app = Flask(__name__)

def log_webhook_data(webhook_data, event_type):
    """Log webhook data for testing and verification"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(PROCESSING_DIR, f'webhook_{event_type}_{timestamp}.json')
    
    with open(log_file, 'w') as f:
        json.dump(webhook_data, f, indent=2)
    
    logger.info(f"Webhook data logged to: {log_file}")
    return log_file

def extract_repo_info(webhook_data):
    """Extract useful repository information from webhook data"""
    repo_info = {
        'repository_name': webhook_data['repository']['name'],
        'repository_url': webhook_data['repository']['clone_url'],
        'ssh_url': webhook_data['repository']['ssh_url'],
        'branch': webhook_data['ref'].split('/')[-1] if 'ref' in webhook_data else 'main',
        'commit_sha': webhook_data['head_commit']['id'] if webhook_data.get('head_commit') else None,
        'commit_message': webhook_data['head_commit']['message'] if webhook_data.get('head_commit') else None,
        'author': webhook_data['head_commit']['author']['name'] if webhook_data.get('head_commit') else None,
        'modified_files': [],
        'added_files': [],
        'removed_files': []
    }
    
    # Extract file changes
    if webhook_data.get('head_commit'):
        repo_info['modified_files'] = webhook_data['head_commit'].get('modified', [])
        repo_info['added_files'] = webhook_data['head_commit'].get('added', [])
        repo_info['removed_files'] = webhook_data['head_commit'].get('removed', [])
    
    return repo_info

def clone_or_pull_repository(repo_info):
    """Clone repository or pull latest changes using GitHub token"""
    repo_name = repo_info['repository_name']
    clone_dir = os.path.join(REPO_CLONE_DIR, repo_name)
    
    # Create authenticated URL using GitHub token
    repo_url = repo_info['repository_url']
    if GITHUB_TOKEN:
        # Replace https://github.com/ with https://TOKEN@github.com/
        auth_url = repo_url.replace('https://github.com/', f'https://{GITHUB_TOKEN}@github.com/')
    else:
        auth_url = repo_url
        logger.warning("No GitHub token configured - using public access")
    
    os.makedirs(REPO_CLONE_DIR, exist_ok=True)
    
    # If directory exists, try to pull instead of clone
    if os.path.exists(clone_dir):
        logger.info(f"Repository directory exists, pulling latest changes")
        
        # Change to repo directory and pull
        cmd = ['git', '-C', clone_dir, 'pull', 'origin', repo_info['branch']]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning(f"Pull failed, attempting fresh clone: {result.stderr}")
            shutil.rmtree(clone_dir)
        else:
            logger.info(f"Successfully pulled latest changes")
            return clone_dir
    
    # Clone repository
    cmd = [
        'git', 'clone', 
        '--branch', repo_info['branch'],
        '--depth', '1',
        auth_url,
        clone_dir
    ]
    
    logger.info(f"Cloning repository from {repo_url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"Failed to clone repository: {result.stderr}")
        return None
    
    logger.info(f"Repository cloned to: {clone_dir}")
    return clone_dir

def deploy_locally(source_dir, repo_info):
    """Deploy files to local deployment directory"""
    if not os.path.exists(LOCAL_DEPLOY_DIR):
        os.makedirs(LOCAL_DEPLOY_DIR, exist_ok=True)
        logger.info(f"Created local deployment directory: {LOCAL_DEPLOY_DIR}")
    
    # Use rsync to sync files locally
    rsync_cmd = [
        'rsync',
        '-avz',
        '--delete',
        f'{source_dir}/',
        LOCAL_DEPLOY_DIR
    ]
    
    logger.info(f"Deploying to local directory: {LOCAL_DEPLOY_DIR}")
    
    result = subprocess.run(rsync_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info(f"Successfully deployed to {LOCAL_DEPLOY_DIR}")
        return True
    else:
        logger.error(f"Failed to deploy locally: {result.stderr}")
        return False

def process_deployment(webhook_data):
    """Process the deployment based on webhook data"""
    repo_info = extract_repo_info(webhook_data)
    
    logger.info(f"Processing deployment for {repo_info['repository_name']}")
    logger.info(f"Branch: {repo_info['branch']}, Commit: {repo_info['commit_sha']}")
    logger.info(f"Commit message: {repo_info['commit_message']}")
    logger.info(f"Author: {repo_info['author']}")
    
    # Clone or pull repository
    clone_dir = clone_or_pull_repository(repo_info)
    if not clone_dir:
        return False
    
    # Deploy locally first
    deployment_success = deploy_locally(clone_dir, repo_info)
    
    if deployment_success:
        logger.info("Local deployment completed successfully")
        
        # TODO: Future enhancement - deploy to remote servers
        # for server_name, server_config in TARGET_SERVERS.items():
        #     success = deploy_to_server(server_config, clone_dir, repo_info)
        #     if not success:
        #         deployment_success = False
    
    # Note: We're not cleaning up the cloned directory anymore 
    # so we can do incremental pulls instead of full clones
    
    return deployment_success

def verify_signature(payload_body, signature_header, secret):
    """Verify GitHub webhook signature"""
    if not signature_header:
        return False
    
    # Compute expected signature
    hash_object = hmac.new(secret, msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(expected_signature, signature_header)

@app.route('/webhook', methods=['POST'])
@app.route('/deploy-hook', methods=['POST'])  # Add your custom path
def handle_webhook():
    """Handle GitHub webhook requests"""
    
    payload_body = request.data  # Raw bytes for HMAC
    signature_header = request.headers.get('X-Hub-Signature-256')
    event_type = request.headers.get('X-GitHub-Event')
    
    logger.info(f"Received webhook event: {event_type}")
    
    # Verify signature if secret is configured
    if WEBHOOK_SECRET:
        if not verify_signature(payload_body, signature_header, WEBHOOK_SECRET):
            logger.error("Webhook signature verification failed")
            return jsonify({'status': 'error', 'message': 'Invalid signature'}), 401
    else:
        logger.warning("No webhook secret configured - skipping signature verification")
    
    # Parse webhook data
    try:
        webhook_data = request.get_json()
        if not webhook_data:
            logger.error("No JSON data in webhook request")
            return jsonify({'status': 'error', 'message': 'No JSON data'}), 400
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
    
    # Log webhook data for testing
    log_file = log_webhook_data(webhook_data, event_type)
    
    # Only process push events
    if event_type != 'push':
        logger.info(f"Ignoring event type: {event_type}")
        return jsonify({'status': 'ignored', 'event': event_type}), 200
    
    # Check if it's the target branch
    if webhook_data.get('ref') != TARGET_BRANCH:
        logger.info(f"Ignoring push to branch: {webhook_data.get('ref')}")
        return jsonify({'status': 'ignored', 'reason': 'wrong branch'}), 200
    
    # Check if it's the target repository
    repo_full_name = webhook_data.get('repository', {}).get('full_name', '')
    if repo_full_name != TARGET_REPO:
        logger.info(f"Ignoring push to repository: {repo_full_name}")
        return jsonify({'status': 'ignored', 'reason': 'wrong repository'}), 200
    
    # Process deployment
    try:
        success = process_deployment(webhook_data)
        if success:
            logger.info("Deployment completed successfully")
            return jsonify({'status': 'success', 'message': 'Deployment completed'}), 200
        else:
            logger.error("Deployment failed")
            return jsonify({'status': 'error', 'message': 'Deployment failed'}), 500
    except Exception as e:
        logger.error(f"Error during deployment: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200

@app.route('/logs', methods=['GET'])
def get_recent_logs():
    """Get recent webhook logs for testing"""
    try:
        log_files = []
        for file in os.listdir(PROCESSING_DIR):
            if file.endswith('.json'):
                file_path = os.path.join(PROCESSING_DIR, file)
                stat = os.stat(file_path)
                log_files.append({
                    'filename': file,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({'logs': log_files[:10]}), 200  # Return last 10 logs
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Check GitHub token
    if not GITHUB_TOKEN:
        logger.warning("No GITHUB_TOKEN environment variable set - only public repositories will work")
    
    # Check webhook secret
    if not WEBHOOK_SECRET:
        logger.warning("No WEBHOOK_SECRET environment variable set - signature verification will be skipped")
    
    # Create local deployment directory if it doesn't exist
    if not os.path.exists(LOCAL_DEPLOY_DIR):
        try:
            os.makedirs(LOCAL_DEPLOY_DIR, exist_ok=True)
            logger.info(f"Created local deployment directory: {LOCAL_DEPLOY_DIR}")
        except Exception as e:
            logger.error(f"Failed to create local deployment directory: {e}")
            logger.info("Deployment will happen in /tmp/deployment instead")
            LOCAL_DEPLOY_DIR = "/tmp/deployment"
            os.makedirs(LOCAL_DEPLOY_DIR, exist_ok=True)
    
    # Use port 5000 as requested
    port = int(os.environ.get('WEBHOOK_PORT', 5000))
    logger.info(f"Starting GitHub webhook server on port {port}")
    logger.info(f"Target repository: {TARGET_REPO}")
    logger.info(f"Target branch: {TARGET_BRANCH}")
    logger.info(f"Local deployment directory: {LOCAL_DEPLOY_DIR}")
    app.run(host='0.0.0.0', port=port, debug=False)