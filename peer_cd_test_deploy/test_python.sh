#!/bin/bash

for file in "$@"; do
    echo "Checking: $file"
    python3 -m py_compile "$file" || exit 1
done