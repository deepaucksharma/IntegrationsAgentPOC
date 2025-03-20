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

# Check if service newrelic-infra_agent is running
if systemctl is-active --quiet newrelic-infra_agent 2>/dev/null || service newrelic-infra_agent status >/dev/null 2>&1; then
    echo "Service newrelic-infra_agent is running"
else
    echo "Service newrelic-infra_agent is not running"
    exit 1
fi


# Check if process newrelic-infra_agent is running
if pgrep -f "newrelic-infra_agent" >/dev/null; then
    echo "Process newrelic-infra_agent is running"
else
    echo "Process newrelic-infra_agent is not running"
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