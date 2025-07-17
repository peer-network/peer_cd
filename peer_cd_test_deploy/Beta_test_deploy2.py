#!/usr/bin/env python3
"""
Post-Deployment Script for Testing and Remote Deployment
Runs unit tests (Python, PHP, Bash) and syncs specific directories to remote servers

This is the switchboard for DevOps, as the all (most) of the DevOps.
So this is teh infrastructure for DevOps 
"""

import os
import sys
import logging
import subprocess
import json
import glob
from datetime import datetime
from pathlib import Path

### Get environment variables passed from webhook
##  
REPO_NAME = os.environ.get('REPO_NAME', 'unknown')
REPO_BRANCH = os.environ.get('REPO_BRANCH', 'unknown')
COMMIT_SHA = os.environ.get('COMMIT_SHA', 'unknown')
COMMIT_MESSAGE = os.environ.get('COMMIT_MESSAGE', 'unknown')
AUTHOR = os.environ.get('AUTHOR', 'unknown')
DEPLOY_DIR = os.environ.get('DEPLOY_DIR', '/opt/application/')
LOCAL_TEST_DIR = os.environ.get('LOCAL_TEST_DIR', '/opt/application/peer_cd_test_deploy/')

# Configuration
LOG_DIR = '/var/log/webhook/'
SSH_KEY_PATH = "/home/ubuntu/.ssh/rsync-key"

# Directory-specific deployment configuration
DEPLOYMENT_MAPPINGS = {
    'Python3_webhook': {
        'source_dir': 'Python3_webhook',
        'target_server': 'local',
        'target_path': '~/myenv/peer_cd/Python3_webhook',
        'user': 'ubuntu',
        'ip': None,  # Local deployment
        'description': 'Python webhook to local server'
    },
    'peer_cd_test_deploy': {
        'source_dir': 'peer_cd_test_deploy',
        'target_server': 'local',
        'target_path': '/opt/application/peer_cd_test_deploy',
        'user': 'ubuntu',
        'ip': None,  # Local deployment
        'description': 'Test deployment files to local server'
    },
    'monitoring-stack': {
        'source_dir': 'monitoring-stack',
        'target_server': 'monitor',
        'target_path': '/home/ubuntu/peer_cd/monitoring-stack',
        'user': 'ubuntu',
        'ip': '172.16.0.20',
        'description': 'Monitoring stack to monitor server'
    },
    'php-webhook': {
        'source_dir': 'php-webhook',
        'target_server': 'deploy-server',
        'target_path': '/home/ubuntu/deploy-scripts',
        'user': 'ubuntu',
        'ip': '172.16.10.194',
        'description': 'PHP webhook to deploy server'
    }
}

# Test configuration (unchanged)
TEST_CONFIGS = {
    'python': {
        'enabled': True,
        'extension': '.py',
        'command': ['bash', 'test_python.sh'],
        'timeout': 60
    },
    'php': {
        'enabled': True,
        'extension': '.php',
        'command': ['bash', 'test_php.sh'],
        'timeout': 60
    },
    'bash': {
        'enabled': True,
        'extension': '.sh',
        'command': ['bash', 'test_bash.sh'],
        'timeout': 60
    }
}
### Use the logging file for the deployment as the webhook
##  this initalize the log for the deployment side of the ci/cd (deploy)
##
def setup_logging():
    """Setup logging to use the same log file as webhook"""
    log_file = os.path.join(LOG_DIR, 'webhook.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('post_deploy')

###  Look above
logger = setup_logging()

### What to log 
##  Log most data from the testing and deploy
##
def log_deployment_info():
    """Log deployment information"""
    logger.info("=" * 60)
    logger.info("POST-DEPLOYMENT SCRIPT STARTED")
    logger.info("=" * 60)
    logger.info(f"Repository: {REPO_NAME}")
    logger.info(f"Branch: {REPO_BRANCH}")
    logger.info(f"Commit: {COMMIT_SHA}")
    logger.info(f"Message: {COMMIT_MESSAGE}")
    logger.info(f"Author: {AUTHOR}")
    logger.info(f"Deploy Directory: {DEPLOY_DIR}")
    logger.info("=" * 60)

### Setup testing for the code updates for DevOps
##  For now only test for syntax (linting) 
##  Maybe more later set testing of all set types of files
## 
def run_tests():
    """Run unit tests for Python, PHP, and Bash"""
    logger.info("Starting unit tests...")
    
    test_results = {}
    overall_success = True
    
    for test_type, config in TEST_CONFIGS.items():
        if not config['enabled']:
            logger.info(f"Skipping {test_type} tests (disabled)")
            continue
            
        test_file = os.path.join(LOCAL_TEST_DIR, config['test_file'])
        
        if not os.path.exists(test_file):
            logger.warning(f"Test file not found: {test_file}")
            test_results[test_type] = {'status': 'skipped', 'reason': 'test file not found'}
            continue
        
        logger.info(f"Running {test_type} tests...")
        
        try:
            # Change to deploy directory to run tests
            # Set to local testing dir
            logger.info(f"Running {test_type} test on {len(files_to_test)} files")

            result = subprocess.run(
                config['command'],
                cwd=DEPLOY_DIR,
                capture_output=True,
                text=True,
                timeout=config['timeout']
            )
            
            if result.returncode == 0:
                logger.info(f"{test_type} tests PASSED")
                test_results[test_type] = {'status': 'passed', 'output': result.stdout}
            else:
                logger.error(f"{test_type} tests FAILED")
                logger.error(f"Exit code: {result.returncode}")
                if result.stderr:
                    logger.error(f"Error output: {result.stderr}")
                test_results[test_type] = {
                    'status': 'failed', 
                    'exit_code': result.returncode,
                    'stderr': result.stderr,
                    'stdout': result.stdout
                }
                overall_success = False
                
        except subprocess.TimeoutExpired:
            logger.error(f"{test_type} tests TIMED OUT after {config['timeout']} seconds")
            test_results[test_type] = {'status': 'timeout'}
            overall_success = False
            
        except Exception as e:
            logger.error(f"Error running {test_type} tests: {str(e)}")
            test_results[test_type] = {'status': 'error', 'error': str(e)}
            overall_success = False
    
    # Log test summary
    logger.info("=" * 40)
    logger.info("TEST SUMMARY")
    logger.info("=" * 40)
    for test_type, result in test_results.items():
        logger.info(f"{test_type.upper()}: {result['status'].upper()}")
    logger.info("=" * 40)
    
    return overall_success, test_results

def deploy_directory_locally(mapping_config, mapping_name):
    """Deploy a specific directory locally using rsync"""
    source_path = os.path.join(DEPLOY_DIR, mapping_config['source_dir'])
    target_path = mapping_config['target_path']
    
    # Expand tilde in target path
    if target_path.startswith('~/'):
        target_path = os.path.expanduser(target_path)
    
    logger.info(f"Deploying {mapping_name} locally: {source_path} -> {target_path}")
    
    # Check if source directory exists
    if not os.path.exists(source_path):
        logger.warning(f"Source directory not found: {source_path}")
        return False
    
    # Create target directory if it doesn't exist
    try:
        os.makedirs(target_path, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create target directory {target_path}: {str(e)}")
        return False
    
    # Rsync command for local deployment
    rsync_cmd = [
        'rsync',
        '-avz',
        '--delete',
        f'{source_path}/',
        f'{target_path}/'
    ]
    
    try:
        result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info(f"Successfully deployed {mapping_name} locally")
            return True
        else:
            logger.error(f"Failed to deploy {mapping_name} locally")
            logger.error(f"Exit code: {result.returncode}")
            if result.stderr:
                logger.error(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Local deployment of {mapping_name} timed out")
        return False
    except Exception as e:
        logger.error(f"Error deploying {mapping_name} locally: {str(e)}")
        return False

def deploy_directory_remotely(mapping_config, mapping_name):
    """Deploy a specific directory to a remote server using rsync over SSH"""
    source_path = os.path.join(DEPLOY_DIR, mapping_config['source_dir'])
    target_path = mapping_config['target_path']
    server_ip = mapping_config['ip']
    server_user = mapping_config['user']
    
    logger.info(f"Deploying {mapping_name} to {server_ip}: {source_path} -> {target_path}")
    
    # Check if source directory exists
    if not os.path.exists(source_path):
        logger.warning(f"Source directory not found: {source_path}")
        return False
    
    # Check if SSH key exists
    if not os.path.exists(SSH_KEY_PATH):
        logger.error(f"SSH key not found at {SSH_KEY_PATH}")
        return False
    
    # Create target directory on remote server first
    create_dir_cmd = [
        'ssh',
        '-i', SSH_KEY_PATH,
        '-o', 'StrictHostKeyChecking=no',
        f'{server_user}@{server_ip}',
        f'mkdir -p {target_path}'
    ]
    
    try:
        subprocess.run(create_dir_cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        logger.warning(f"Could not create remote directory (may already exist): {str(e)}")
    
    # Rsync command for remote deployment
    rsync_cmd = [
        'rsync',
        '-avz',
        '--delete',
        '-e', f'ssh -i {SSH_KEY_PATH} -o StrictHostKeyChecking=no',
        f'{source_path}/',
        f'{server_user}@{server_ip}:{target_path}/'
    ]
    
    try:
        result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info(f"Successfully deployed {mapping_name} to {server_ip}")
            return True
        else:
            logger.error(f"Failed to deploy {mapping_name} to {server_ip}")
            logger.error(f"Exit code: {result.returncode}")
            if result.stderr:
                logger.error(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Remote deployment of {mapping_name} timed out")
        return False
    except Exception as e:
        logger.error(f"Error deploying {mapping_name} remotely: {str(e)}")
        return False

def deploy_directories():
    """Deploy all configured directories to their respective targets"""
    logger.info("Starting directory-specific deployment...")
    
    deployment_results = {}
    overall_success = True
    
    for mapping_name, mapping_config in DEPLOYMENT_MAPPINGS.items():
        logger.info(f"Processing {mapping_name}: {mapping_config['description']}")
        
        # Check if source directory exists in the deployed code
        source_path = os.path.join(DEPLOY_DIR, mapping_config['source_dir'])
        if not os.path.exists(source_path):
            logger.warning(f"Source directory {mapping_config['source_dir']} not found in deployment - skipping")
            deployment_results[mapping_name] = {'status': 'skipped', 'reason': 'source not found'}
            continue
        
        # Deploy based on target server type
        if mapping_config['target_server'] == 'local' or mapping_config['ip'] is None:
            success = deploy_directory_locally(mapping_config, mapping_name)
        else:
            success = deploy_directory_remotely(mapping_config, mapping_name)
        
        deployment_results[mapping_name] = {
            'status': 'success' if success else 'failed',
            'target_server': mapping_config['target_server'],
            'target_path': mapping_config['target_path']
        }
        
        if not success:
            overall_success = False
    
    # Log deployment summary
    logger.info("=" * 50)
    logger.info("DIRECTORY DEPLOYMENT SUMMARY")
    logger.info("=" * 50)
    for mapping_name, result in deployment_results.items():
        status = result['status'].upper()
        target = result.get('target_path', 'N/A')
        logger.info(f"{mapping_name}: {status} -> {target}")
    logger.info("=" * 50)
    
    return overall_success, deployment_results

def save_deployment_report(test_results, deployment_results):
    """Save a detailed deployment report"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'repository': REPO_NAME,
        'branch': REPO_BRANCH,
        'commit_sha': COMMIT_SHA,
        'commit_message': COMMIT_MESSAGE,
        'author': AUTHOR,
        'test_results': test_results,
        'deployment_results': deployment_results
    }
    
    report_file = os.path.join(LOG_DIR, 'events', f'deployment_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    
    try:
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Deployment report saved to: {report_file}")
    except Exception as e:
        logger.error(f"Failed to save deployment report: {str(e)}")

def main():
    """Main post-deployment workflow"""
    log_deployment_info()
    
    # Step 1: Run unit tests
    test_success, test_results = run_tests()
    
    if not test_success:
        logger.error("Unit tests failed - aborting remote deployment")
        save_deployment_report(test_results, {})
        return 1
    
    # Step 2: Deploy directories to their respective targets
    deploy_success, deployment_results = deploy_directories()
    
    # Step 3: Save deployment report
    save_deployment_report(test_results, deployment_results)
    
    # Final status
    if test_success and deploy_success:
        logger.info("POST-DEPLOYMENT COMPLETED SUCCESSFULLY")
        return 0
    else:
        logger.error("POST-DEPLOYMENT FAILED")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)