#!/bin/bash

for file in "$@"; do
    echo "Checking Bash: $file"
    bash -n "$file" || exit 1
done