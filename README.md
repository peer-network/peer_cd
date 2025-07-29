# Peer CD  
This is the repository of Peer Networks Continuos Deployment (CD) Code.  


# Continuos Deployment

## This repo is to track files and changes in Peers' Continuos Deployment.

---

## PHP Webhook
### peer_backend
Set to catch the PHP API to start a build.

There are 3 files that are needed
* peer-deploy-hok.php
* deploy-backend.sh
* payload.json
  * for testing

There is a test curl command that can run this deploy script as a test.

```
curl -X POST https://peer-network.eu/deploy-hook -H "Content-Type: application/json"   -H "X-Hub-Signature-256: sha256=$SIGNATURE" --data-binary @payload.json
```

## Monitor database
### peer_monitor

New server added to the beta-testing group.
It is running a script to test the prod database or "The Feed" of Peer.
if there is any thing wrong with the database, an alert is send to Telegram
An example

![image](https://github.com/user-attachments/assets/3ce8670f-7e94-4936-b634-0cc304cb5f35)


There is a cron job that runs the monitor every 3 minutes.

```
*/3 *   * * *   root    bash /home/ubuntu/peer_cd/monitoring-stack/scripts/monitor-api-py.sh >> /var/log/postman_logs/cron.log 2>&1
```

## GitHub Push to server
### to have a Github push to propigate to the CD servers to update the code when needed.

To have pushes to this repo to be be 'pushed' to the repected servers.
This CD will be split between
* Main
  * This brach will push changes for monitoring Prod systems
* Dev
  * This brach will push to the testing envirnment

DevOps then can push to Dev easily and can test there changes.  When all parties are happy then a merge to Main and push to effect Prod.

The /opt/application/ directory

```
.
├── LICENSE
├── Python3_webhooK           (main webhook for the infrasctuture)
│   ├── Beta_test_Py3_webhook.py
│   └── Beta_test_Py3_webhook2.py  (current)
├── README.md
├── monitoring-stack    (DevOps monitoring)
│   ├── postman_collection
│   │   ├── postman_collections.json
│   │   └── postman_environment.json
│   └── scripts
│       ├── monitor_api.sh
│       └── monitor_api_py.ph
├── payload.json              (test .json)
├── peer_cd_test_deploy       (Where the test and deploy scripts are located)
│   ├── Beta_test_deploy.py   (Called from Python3_webhook2.py)
│   ├── test_bash.sh
│   ├── test_php.sh
│   └── test_python.sh
├── php-webhook               (update the backend)
│   ├── deploy-backend.sh
│   └── peer-deploy-hook.php
├── restart-php.sh
└── update-database.sh
```

There is are ssh-keys to allow the transfer to the update to the remote servers. rsync-key  
This key will only push github changes to the needed places. 


```
# Directory-specific deployment configuration
DEPLOYMENT_MAPPINGS = {
    'Python3_webhook': {
        'source_dir': 'Python3_webhook',
        'target_server': 'local',
        'target_path': '~/myenv/peer_cd/Python3_webhook',
        'user': 'ubuntu',
        'ip': None,  # Local deployment
        'description': 'Python webhook to local server',
        'excludes': []
    },
    'peer_cd_test_deploy': {
        'source_dir': 'peer_cd_test_deploy',
        'target_server': 'local',
        'target_path': '/opt/application/peer_cd_test_deploy',
        'user': 'ubuntu',
        'ip': None,  # Local deployment
        'description': 'Test deployment files to local server',
        'excludes': []
    },
    'monitoring-stack': {
        'source_dir': 'monitoring-stack',
        'target_server': 'monitor',
        'target_path': '/home/ubuntu/peer_cd/monitoring-stack',
        'user': 'ubuntu',
        'ip': '172.16.0.20',
        'description': 'Monitoring stack to monitor server',
        'excludes': []
    },
    'mintbot': {
        'source_dir': 'mintbot',
        'target_server': 'monitor',
        'target_path': '/home/ubuntu/peer_cd/mintbot',
        'user': 'ubuntu',
        'ip': '172.16.0.20',
        'description': 'Monitoring for gem token queries',
        'excludes': [
            '.env',
            'secrets/*',
            'logs/*'
            ]
    },
    'php-webhook': {
        'source_dir': 'php-webhook',
        'target_server': 'deploy-server',
        'target_path': '/home/ubuntu/deploy-scripts',
        'user': 'ubuntu',
        'ip': '172.16.10.194',
        'description': 'PHP webhook to deploy server',
        'excludes': []
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
```