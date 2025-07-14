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


# Your target GitHub repo
TARGET_REPO = "peer-network/peer_cd"

# Push to dev will triger web-hook.
TARGET_BRANCH = "refs/heads/dev"
SSH_KEY_PATH = "/home/ubuntu/.ssh/id_rsa"


# Configuration

LOG_DIR = '/var/log/webhook/'
PROCESSING_DIR = '/var/log/webhook/events/'
REPO_CLONE_DIR = '/tmp/peer_cd/'

# Target servers configuration
TARGET_SERVERS = {
    'monitor': {
        'ip': '172.16.0.20',
        'hostname': 'monitor',
        'deploy_path': '/opt/application/',  # Adjust as needed
        'user': 'deploy'  # Adjust as needed
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

def verify_signature(payload_body, signature_header):
    """Verify GitHub webhook signature"""
    if not signature_header:
        return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET,
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature_header)

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

def clone_repository(repo_info):
    """Clone repository to temporary directory"""
    repo_name = repo_info['repository_name']
    clone_dir = os.path.join(REPO_CLONE_DIR, repo_name)
    
    # Clean up existing directory
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)
    
    os.makedirs(REPO_CLONE_DIR, exist_ok=True)
    
    # Clone repository
    cmd = [
        'git', 'clone', 
        '--branch', repo_info['branch'],
        '--depth', '1',
        repo_info['repository_url'],
        clone_dir
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Failed to clone repository: {result.stderr}")
        return None
    
    logger.info(f"Repository cloned to: {clone_dir}")
    return clone_dir

def deploy_to_server(server_config, source_dir, repo_info):
    """Deploy files to target server using rsync over SSH"""
    server_name = server_config['hostname']
    server_ip = server_config['ip']
    server_user = server_config['user']
    deploy_path = server_config['deploy_path']
    
    # Rsync command
    rsync_cmd = [
        'rsync',
        '-avz',
        '--delete',
        '-e', f'ssh -i {SSH_KEY_PATH} -o StrictHostKeyChecking=no',
        f'{source_dir}/',
        f'{server_user}@{server_ip}:{deploy_path}'
    ]
    
    logger.info(f"Deploying to {server_name} ({server_ip})")
    
    result = subprocess.run(rsync_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info(f"Successfully deployed to {server_name}")
        return True
    else:
        logger.error(f"Failed to deploy to {server_name}: {result.stderr}")
        return False

def process_deployment(webhook_data):
    """Process the deployment based on webhook data"""
    repo_info = extract_repo_info(webhook_data)
    
    logger.info(f"Processing deployment for {repo_info['repository_name']}")
    logger.info(f"Branch: {repo_info['branch']}, Commit: {repo_info['commit_sha']}")
    
    # Clone repository
    clone_dir = clone_repository(repo_info)
    if not clone_dir:
        return False
    
    # Deploy to each target server
    deployment_success = True
    for server_name, server_config in TARGET_SERVERS.items():
        success = deploy_to_server(server_config, clone_dir, repo_info)
        if not success:
            deployment_success = False
    
    # Clean up cloned directory
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)
    
    return deployment_success

@app.route('/webhook', methods=['POST'])
@app.route('/deploy-hook', methods=['POST'])  # Add your custom path
def handle_webhook():
    """Handle GitHub webhook requests"""
    signature = request.headers.get('X-Hub-Signature-256')
    event_type = request.headers.get('X-GitHub-Event')
    
    # Verify signature
    if not verify_signature(request.data, signature):
        logger.warning("Invalid webhook signature", signature)
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse webhook data
    webhook_data = request.get_json()
    
    # Log webhook data for testing
    log_file = log_webhook_data(webhook_data, event_type)
    
    # Only process push events
    if event_type != 'push':
        logger.info(f"Ignoring event type: {event_type}")
        return jsonify({'status': 'ignored', 'event': event_type}), 200
    
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
    # Check SSH key exists
    if not os.path.exists(SSH_KEY_PATH):
        logger.error(f"SSH key not found at {SSH_KEY_PATH}")
        exit(1)
    
    # Use port 5000 as requested
    port = int(os.environ.get('WEBHOOK_PORT', 5000))
    logger.info(f"Starting GitHub webhook server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)