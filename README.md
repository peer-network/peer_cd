# Peer CD  
This is the repository of Peer Networks Continuos Deployment (CD) Code.  


# Welcome to Continuous Deployment (CD) Wiki for **Peer Network** 

### This page serves as the single orientation/explainer point for DevOps and Administrators for Peer.

---

## 🚀 What is Peer Network?

Peer Network is a blockchain-integrated social network where users post content, earn tokens, Chat, and importantly (Monetize Participation).

---

## 🧱 Architecture Overview

The system is made up of multiple coordinated repositories:

| Component | Description |
|----------|-------------|
| [`peer_backend`](https://github.com/peer-network/peer_backend) | Main GraphQL API: users, content, chat, wallet, moderation |
| [`peer_backend_CI/CD`](https://github.com/peer-network/peer_backend_ci-cd) | Main DevOps repository |
| [`peer_cd`](https://github.com/peer-network/peer_cd) | This repo |

Each client connects to the backend via GraphQL, and the backend handles blockchain interaction and rewards.

## Peer CD

### Please read the wiki for more information implimenting new code to this repo.

This repo is to facilitate automatic updates to the other back-end servers from DevOps.  This allows DevOps to push to this repo and have those changes apply to the **testing** environment of Peer.  There is a webhook monitoring this repo for any pushs to `dev` branch. The `main` branch pushes to **production** (when verified). 

The setup of the repo is part of how the webhook work and the placement of the scrips from DevOps.  

Each directory has a point where the code is copied (`rsync`) remotely or locally. 

## Format of Peer CD

As of 04.08.2025
The directory structure is:

```.
├── mintbot
│   ├── scripts
│   └── secrets
├── monitoring-stack
│   ├── postman_collection
│   └── scripts
├── peer_cd_test_deploy
├── php-webhook
└── Python3_webhooK
```

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