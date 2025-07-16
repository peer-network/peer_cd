#!/bin/bash

find "$1" -name "*.py" -exec python3 -m py_compile {} \;