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

### The current main projects are 
| Project | Description |
|----------|-------------|
|- `mintbot` | Mining token system check runs once a day at 10:00 CET |
|- `monitor-stack` | Postman check for the backend updates |
|- `php_webhook` | PHP Datebase monitor |
|- `Python3_webhook` & `peer_cd_test_deploy`| This is the deployment code for Peer CD |

The current main projects are
Project 	Description
- mintbot 	Mining token system check runs once a day at 10:00 CET
- monitor-stack 	Postman check for the backend updates
- php_webhook 	PHP Datebase monitor
- Python3_webhook & peer_cd_test_deploy 	This is the deployment code for Peer CD
Python3_webhook & peer_cd_test_deploy
These directories contain the webhook for this repo. The webhook listens for a "push" to Github. Then the script sorts the target directory and then calls the peer test and deploy script to perforem unit tests (Linting for now) and rsync to the remote servers. The (local server is beta_testing jumphost) is is where a local copy of of this repo and active scripts resides.

