# Peer CD  
This is the repository of Peer Networks Continuos Deployment (CD) Code.  


# Continuos Deplaoyment

## This repo is to track files adn changes in Peers' Continuos Deployment.

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


