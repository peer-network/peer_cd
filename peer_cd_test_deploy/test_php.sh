#!/bin/bash

for file in "$@"; do
    echo "Checking PHP: $file"
    php -l "$file" || exit 1
done