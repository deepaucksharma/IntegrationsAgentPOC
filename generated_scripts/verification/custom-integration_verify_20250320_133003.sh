#!/bin/bash
set -e

# Error handler
trap 'handle_error $? $LINENO' ERR

handle_error() {
    echo "Error $1 occurred on line $2"
    exit 1
}


# Custom verification checks

# Generic verification checks

# Check if process newrelic-custom is running
if pgrep -f "newrelic-custom" >/dev/null; then
    echo "Process newrelic-custom is running"
else
    echo "Process newrelic-custom is not running"
    exit 1
fi


# Check if port 8080 is listening
if command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep -q ":8080\s"; then
        echo "Port 8080 is listening"
    else
        echo "Port 8080 is not listening"
        exit 1
    fi
elif command -v ss >/dev/null 2>&1; then
    if ss -tuln | grep -q ":8080\s"; then
        echo "Port 8080 is listening"
    else
        echo "Port 8080 is not listening"
        exit 1
    fi
else
    echo "Cannot check port 8080: netstat/ss commands not available"
    exit 1
fi


# Configuration validation

echo "All verification checks passed successfully"