#!/bin/bash

# Check if monitoring agent is running
if command -v monitoring-agent &> /dev/null; then
    # Check if agent is responding
    if monitoring-agent status | grep -q "running"; then
        echo "Monitoring agent is installed and running"
        exit 0
    else
        echo "Monitoring agent is installed but not running"
        exit 1
    fi
else
    echo "Monitoring agent is not installed"
    exit 1
fi 