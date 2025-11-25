#!/usr/bin/env python3
"""
GitHub Webhook Server for Jump Host Deployment
Handles GitHub push events and deploys to target servers via rsync/ssh
This will allo peer to puch to various servers on the admin adn backend lines.

The target of the webhook in the testing jump host. 
When the push is successful then a bash script rsyncs the other servers the chagnes.
Set for testing set pull, done
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

# Local deployment directory - where we'll keep the synced code
LOCAL_TEST_DIR = "/opt/application/peer_cd_test_deploy"

# Configuration
LOG_DIR = '/var/log/webhook/'
PROCESSING_DIR = '/var/log/webhook/events/'
REPO_CLONE_DIR = '/tmp/peer_cd/'

# Expected directories in the repository
EXPECTED_DIRECTORIES = [
    'Python3_webhook',
    'peer_cd_test_deploy',
    'monitoring-stack',
    'php-webhook'
]

# Target servers configuration (for future rsync deployment)
TARGET_SERVERS = {
    'monitor': {
        'ip': '172.16.0.20',
        'hostname': 'monitor',
        'deploy_path': '/opt/application/',
        'user': 'deploy'
    }
}

### Initial Setup logging
##  Is the directories for logging there

# Setup logging
def setup_logging():
    """Setup logging configuration"""
    os.makedirs(LOG_DIR, exist_ok=True)   # /var/log/webhook/
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
### Gather and log the actions from the webhook
##  What it is, and does it work
##  log the errors when needed
def log_webhook_data(webhook_data, event_type):
    """Log webhook data for testing and verification"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(PROCESSING_DIR, f'webhook_{event_type}_{timestamp}.json')
    
    with open(log_file, 'w') as f:
        json.dump(webhook_data, f, indent=2)
    
    logger.info(f"Webhook data logged to: {log_file}")
    return log_file


### Parse the webhook data
##  sperate the heeder and certificate data from the payload
##  
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
    
    # Extract file changes (The Commits)
    if webhook_data.get('head_commit'):
        repo_info['modified_files'] = webhook_data['head_commit'].get('modified', [])
        repo_info['added_files'] = webhook_data['head_commit'].get('added', [])
        repo_info['removed_files'] = webhook_data['head_commit'].get('removed', [])
    
    return repo_info

### Initalize with clone
##  Then pull the changes from github
##
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
        
        # Reset any local changes first
        reset_cmd = ['git', '-C', clone_dir, 'reset', '--hard', 'HEAD']
        subprocess.run(reset_cmd, capture_output=True, text=True)
        
        # Pull latest changes
        cmd = ['git', '-C', clone_dir, 'pull', 'origin', repo_info['branch']]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        ### remove the clone directory if there need (failed pull, or initialize)
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


### Now deploy to the main (opt/application) directory 
##  Add the updated files from the pull
##  Rsync to the local dir
def validate_repository_structure(clone_dir):
    """Validate that the repository contains expected directories"""
    logger.info("Validating repository structure...")
    
    found_directories = []
    missing_directories = []
    
    for expected_dir in EXPECTED_DIRECTORIES:
        dir_path = os.path.join(clone_dir, expected_dir)
        if os.path.exists(dir_path):
            found_directories.append(expected_dir)
            logger.info(f"Found directory: {expected_dir}")
        else:
            missing_directories.append(expected_dir)
            logger.warning(f"Missing expected directory: {expected_dir}")
    
    if found_directories:
        logger.info(f"Repository structure validation: {len(found_directories)} directories found")
        return True
    else:
        logger.error("No expected directories found in repository")
        return False

def deploy_locally(source_dir, repo_info):
    """Deploy files to local deployment directory"""
    if not os.path.exists(LOCAL_DEPLOY_DIR):
        os.makedirs(LOCAL_DEPLOY_DIR, exist_ok=True)
        logger.info(f"Created local deployment directory: {LOCAL_DEPLOY_DIR}")
    
    # Log deployment start
    logger.info(f"Starting local deployment from {source_dir} to {LOCAL_DEPLOY_DIR}")
    
    # Deploy each expected directory
    deployment_success = True
    for expected_dir in EXPECTED_DIRECTORIES:
        source_path = os.path.join(source_dir, expected_dir)
        if not os.path.exists(source_path):
            logger.warning(f"Skipping {expected_dir} - not found in source")
            continue
        
        target_path = os.path.join(LOCAL_DEPLOY_DIR, expected_dir)
        logger.info(f"Deploying {expected_dir}...")
        
        try:
            # Use rsync for efficient syncing
            # -a: archive mode (preserves permissions, timestamps, etc.)
            # -v: verbose
            # --delete: remove files in destination that don't exist in source
            cmd = [
                'rsync',
                '-av',
                '--delete',
                f'{source_path}/',
                f'{target_path}/'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Successfully deployed {expected_dir}")
            logger.debug(f"rsync output: {result.stdout}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to deploy {expected_dir}: {e.stderr}")
            deployment_success = False
    
    return deployment_success

def run_tests(test_dir):
    """Run tests in the test directory"""
    logger.info(f"Running tests in {test_dir}")
    
    # Look for test scripts or files
    test_scripts = []
    if os.path.exists(test_dir):
        for file in os.listdir(test_dir):
            if file.startswith('test_') and file.endswith('.py'):
                test_scripts.append(os.path.join(test_dir, file))
    
    if not test_scripts:
        logger.warning("No test scripts found")
        return True
    
    # Run each test script
    all_tests_passed = True
    for test_script in test_scripts:
        logger.info(f"Running test script: {test_script}")
        try:
            result = subprocess.run(
                ['python3', test_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"Test passed: {test_script}")
            else:
                logger.error(f"Test failed: {test_script}")
                logger.error(f"Test output: {result.stdout}")
                logger.error(f"Test errors: {result.stderr}")
                all_tests_passed = False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Test timeout: {test_script}")
            all_tests_passed = False
        except Exception as e:
            logger.error(f"Error running test {test_script}: {str(e)}")
            all_tests_passed = False
    
    return all_tests_passed

def process_deployment(webhook_data):
    """Main deployment process"""
    logger.info("Starting deployment process")
    
    # Extract repository information
    repo_info = extract_repo_info(webhook_data)
    logger.info(f"Repository: {repo_info['repository_name']}")
    logger.info(f"Branch: {repo_info['branch']}")
    logger.info(f"Commit: {repo_info['commit_sha']}")
    logger.info(f"Author: {repo_info['author']}")
    logger.info(f"Message: {repo_info['commit_message']}")
    
    # Log file changes
    if repo_info['modified_files']:
        logger.info(f"Modified files: {', '.join(repo_info['modified_files'])}")
    if repo_info['added_files']:
        logger.info(f"Added files: {', '.join(repo_info['added_files'])}")
    if repo_info['removed_files']:
        logger.info(f"Removed files: {', '.join(repo_info['removed_files'])}")
    
    # Clone or pull repository
    clone_dir = clone_or_pull_repository(repo_info)
    if not clone_dir:
        logger.error("Failed to clone/pull repository")
        return False
    
    # Validate repository structure
    if not validate_repository_structure(clone_dir):
        logger.error("Repository structure validation failed")
        return False
    
    # Deploy locally
    deployment_success = deploy_locally(clone_dir, repo_info)
    
    if deployment_success:
        logger.info("Local deployment completed successfully")
        
        # Run tests if test directory exists
        test_path = os.path.join(LOCAL_DEPLOY_DIR, 'peer_cd_test_deploy')
        if os.path.exists(test_path):
            logger.info("Running deployment tests...")
            tests_passed = run_tests(test_path)
            if tests_passed:
                logger.info("All tests passed")
            else:
                logger.warning("Some tests failed - review test logs")
        else:
            logger.info("No test directory found - skipping tests")
    else:
            logger.error(f"Deploy and Test")

    ### End deploy
    
    return deployment_success

### webhook proccess
##  github signature with payload will parse the directories
##
def verify_signature(payload_body, signature_header, secret):
    """Verify GitHub webhook signature"""
    if not signature_header:
        return False
    
    # Compute expected signature
    hash_object = hmac.new(secret, msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(expected_signature, signature_header)

def branch_matches_ref(ref, target_branch):
    """
    Check if the webhook 'ref' matches the target branch.
    Example:
      ref = 'refs/heads/dev'
      target_branch = 'refs/heads/dev'
    Returns True if matches.
    """
    if not ref or not target_branch:
        return False
    return ref.strip() == target_branch.strip()


### Main webhook checking
##  Where from, is valid, github, branch, ...abs
##
@app.route('/webhook', methods=['POST'])
@app.route('/deploy-hook', methods=['POST'])  # Add your custom path
def handle_webhook():
    """Handle GitHub webhook requests"""
    
    payload_body = request.data  # Raw bytes for HMAC
    signature_header = request.headers.get('X-Hub-Signature-256')
    event_type = request.headers.get('X-GitHub-Event')
    
    logger.info(f"=*= Initiated github event proccess =*=")
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
    
    ### Process github action (push & pull_request, branch and repo)
    # Only process push events and pull_request events
    if event_type not in {"push", "pull_request"}:
        logger.info(f"Ignoring event type: {event_type}")
        return jsonify({'status': 'ignored', 'event': event_type}), 200

    # Handle push events
    if event_type == "push":
        ref = webhook_data.get("ref", "")
        if not branch_matches_ref(ref, TARGET_BRANCH):
            logger.info(f"Ignoring push to ref: {ref} (expected: {TARGET_BRANCH})")
            return jsonify({"status": "ignored", "reason": "wrong branch"}), 200

    # Handle pull_request events
    elif event_type == "pull_request":
        action = webhook_data.get("action", "")
        # Only react to meaningful PR actions
        if action not in {"opened", "reopened", "synchronize"}:
            logger.info(f"Ignoring PR action: {action}")
            return jsonify({"status": "ignored", "reason": f"PR action {action}"}), 200

        # Check if PR targets the correct base branch
        base_ref = webhook_data.get("pull_request", {}).get("base", {}).get("ref", "")
        # Convert base_ref to full ref format for comparison
        full_base_ref = f"refs/heads/{base_ref}" if not base_ref.startswith("refs/") else base_ref
        if not branch_matches_ref(full_base_ref, TARGET_BRANCH):
            logger.info(f"Ignoring PR targeting base: {base_ref} (expected: {TARGET_BRANCH})")
            return jsonify({"status": "ignored", "reason": "wrong base branch"}), 200
    
    # Check if it's the target repository
    repo_full_name = webhook_data.get('repository', {}).get('full_name', '')
    if repo_full_name != TARGET_REPO:
        logger.info(f"Ignoring push to repository: {repo_full_name}")
        return jsonify({'status': 'ignored', 'reason': 'wrong repository'}), 200
    
    # Process deployment
    # return status
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

@app.route('/status', methods=['GET'])
def deployment_status():
    """Get deployment status and directory information"""
    try:
        status_info = {
            'local_deploy_dir': LOCAL_DEPLOY_DIR,
            'repo_clone_dir': REPO_CLONE_DIR,
            'target_repo': TARGET_REPO,
            'target_branch': TARGET_BRANCH,
            'expected_directories': EXPECTED_DIRECTORIES,
            'deployed_directories': []
        }
        
        # Check which directories are currently deployed
        if os.path.exists(LOCAL_DEPLOY_DIR):
            for expected_dir in EXPECTED_DIRECTORIES:
                dir_path = os.path.join(LOCAL_DEPLOY_DIR, expected_dir)
                if os.path.exists(dir_path):
                    status_info['deployed_directories'].append({
                        'name': expected_dir,
                        'path': dir_path,
                        'modified': datetime.fromtimestamp(os.path.getmtime(dir_path)).isoformat()
                    })
        
        return jsonify(status_info), 200
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
    
    # Log configuration
    logger.info("=" * 60)
    logger.info("GITHUB WEBHOOK SERVER CONFIGURATION")
    logger.info("=" * 60)
    logger.info(f"Target repository: {TARGET_REPO}")
    logger.info(f"Target branch: {TARGET_BRANCH}")
    logger.info(f"Local deployment directory: {LOCAL_DEPLOY_DIR}")
    logger.info(f"Repository clone directory: {REPO_CLONE_DIR}")
    logger.info(f"Expected directories: {', '.join(EXPECTED_DIRECTORIES)}")
    logger.info(f"Log directory: {LOG_DIR}")
    logger.info("=" * 60)
    
    # Use port 5000 as requested
    port = int(os.environ.get('WEBHOOK_PORT', 5000))
    logger.info(f"Starting GitHub webhook server on port {port}")
    
    ### Flask webserver (simple might need to change later)
    app.run(host='0.0.0.0', port=port, debug=False)

    ### Ende
