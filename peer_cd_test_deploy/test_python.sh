#!/bin/bash

for file in "$@"; do
    echo "Checking Python: $file"
    python3 -m py_compile "$file" || exit 1
done