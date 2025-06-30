#!/bin/bash

## to restart PHP and the database
## sudo or root permissions are required to this script

systemctl restart php8.3-fpm

## remove locks and old data
rm -rf /var/www/peer_beta/peer_backend/vendor/
rm -f  /var/www/peer_beta/peer_backendcomposer.lock

composer install

## set ownership
chown -R www-data:www-data /var/www/peer_beta/
find /var/www/peer_beta/ -type d -exec chmod 755 {} \;
find /var/www/peer_beta/ -type f -exec chmod 644 {} \;
