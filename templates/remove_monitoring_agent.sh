#!/bin/bash

# Remove monitoring agent
echo "Removing monitoring agent..."

# Check if agent is installed
if ! command -v monitoring-agent &> /dev/null; then
    echo "Monitoring agent is not installed."
    exit 0
fi

# Stop the agent service
echo "Stopping monitoring agent service..."
if systemctl is-active --quiet monitoring-agent; then
    systemctl stop monitoring-agent
fi

# Run uninstall script if available
if [ -f /opt/monitoring-agent/uninstall.sh ]; then
    echo "Running uninstall script..."
    /opt/monitoring-agent/uninstall.sh
elif [ -f /usr/local/bin/monitoring-agent-uninstall ]; then
    echo "Running uninstall script..."
    /usr/local/bin/monitoring-agent-uninstall
else
    echo "No uninstall script found, removing manually..."
    rm -f /usr/local/bin/monitoring-agent
    rm -rf /opt/monitoring-agent
fi

# Verify removal
if command -v monitoring-agent &> /dev/null; then
    echo "Failed to remove monitoring agent."
    exit 1
else
    echo "Monitoring agent removed successfully."
    exit 0
fi 