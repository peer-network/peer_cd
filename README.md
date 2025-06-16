# Peer CD  
This is the repository of Peer Networks Continuos Deployment (CD) Code.  


# Continuos Deplaoyment

## This repo is to track files adn changes in Peers' Continus Deployment.

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


