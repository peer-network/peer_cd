#!/bin/bash

find "$1" -name "*.sh" -exec bash -n {} \;