#!/bin/bash

for file in "$@"; do
    echo "Checking: $file"
    bash -n "$file" || exit 1
done