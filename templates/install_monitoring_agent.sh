#!/bin/bash

# Install monitoring agent
echo "Installing monitoring agent..."

# Check if agent is already installed
if command -v monitoring-agent &> /dev/null; then
    echo "Monitoring agent is already installed."
    exit 0
fi

# Download agent
echo "Downloading monitoring agent..."
curl -L https://example.com/monitoring-agent/install.sh -o /tmp/agent-install.sh

# Verify download
if [ ! -f /tmp/agent-install.sh ]; then
    echo "Failed to download monitoring agent."
    exit 1
fi

# Make script executable
chmod +x /tmp/agent-install.sh

# Run installation
echo "Running installation script..."
/tmp/agent-install.sh --api-key="{{ api_key }}" --endpoint="{{ endpoint }}"

# Verify installation
if command -v monitoring-agent &> /dev/null; then
    echo "Monitoring agent installed successfully."
    exit 0
else
    echo "Failed to install monitoring agent."
    exit 1
fi 