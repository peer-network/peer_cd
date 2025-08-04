#!/bin/bash

for file in "$@"; do
    echo "Checking: $file"
    php -l "$file" || exit 1
done