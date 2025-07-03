#!/bin/bash
### This is the backend update script that calls calls ffmpeg, copies the new git code to that main backend dirs.
### Then cleans out the old code and runs the docker compose to rebuild the backend.
### Lastly it will call the backend configureation builder to relink all fo the needed tools


echo "=== Deployment started at $(date) ==="

# Ensure ffmpeg is installed
echo "== Checking and installing ffmpeg =="
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg not found. Exiting...(if this is a new server install manually)"
    exit 1
else
    echo "ffmpeg is already installed, Version $(ffmpeg -version | head -n 1)"
fi

cd /var/www/peer_beta/peer_backend_git || {
    echo "ERROR: Failed to change directory to project folder"
    exit 1
}

echo "== Pulling latest changes... =="
git reset --hard
git pull origin development || {
    echo "* ERROR: Git pull failed *"
    exit 1
}

rm -rf /var/www/peer_beta/peer_backend/src/
rm -rf /var/www/peer_beta/peer_backend/vendor/
rm -rf /var/www/peer_beta/peer_backend/public/
rm -f /var/www/peer_beta/peer_backend/.env.schema
rm -f /var/www/peer_beta/peer_backend/composer.json composer.lock
rm -rf /var/www/peer_beta/peer_backend/sql_files_for_import/
rm -rf /var/www/peer_beta/peer_backend/runtime-data/media/assets/
rm -f /var/www/peer_beta/peer_backend/cd-generate-backend-config.sh
rm -rf /var/www/peer_beta/peer_backend/.git 

cp -r /var/www/peer_beta/peer_backend_git/src/ /var/www/peer_beta/peer_backend/
cp -r /var/www/peer_beta/peer_backend_git/public/ /var/www/peer_beta/peer_backend/  
cp -r /var/www/peer_beta/peer_backend_git/sql_files_for_import/ /var/www/peer_beta/peer_backend/  
cp -r /var/www/peer_beta/peer_backend_git/runtime-data /var/www/peer_beta/peer_backend/

cp /var/www/peer_beta/peer_backend_git/.env.schema /var/www/peer_beta/peer_backend/
cp /var/www/peer_beta/peer_backend_git/composer.json /var/www/peer_beta/peer_backend/
cp /var/www/peer_beta/peer_backend_git/cd-generate-backend-config.sh /var/www/peer_beta/peer_backend/ 
cp -r /var/www/peer_beta/peer_backend_git/.git  /var/www/peer_beta/peer_backend/

# cd into folder
cd /var/www/peer_beta/peer_backend || {
    echo "* ERROR: Failed to switch to backend folder *"
    exit 1
}

 
if [ -f composer.json ]; then
    echo "== Installing Composer dependencies... =="
    /usr/bin/composer install --no-interaction --prefer-dist || {
        echo "* ERROR: Composer install failed *"
        exit 1
    }
fi

# php /var/www/peer_beta/peer_backend/tests/utils/ConfigGeneration/GenerateConfig.php

sh /var/www/peer_beta/peer_backend/cd-generate-backend-config.sh

# already set from the server
#chown -R www-data:www-data /var/www/peer_beta/
#find /var/www/peer_beta/ -type d -exec chmod 755 {} \;
#find /var/www/peer_beta/ -type f -exec chmod 644 {} \;

echo "=== Deployment finished at $(date) ==="