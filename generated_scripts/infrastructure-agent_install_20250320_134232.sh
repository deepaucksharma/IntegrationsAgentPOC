#!/bin/bash

# Error handling
set -e
trap 'echo "Error on line $LINENO"' ERR

# Logging
LOG_FILE="/var/log/infra_agent_install.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "Starting infrastructure agent installation..."

# Verify prerequisites
echo "Verifying prerequisites..."
if ! command -v curl &> /dev/null; then
    echo "Error: curl is required but not installed"
    exit 1
fi

# Create installation directory
echo "Creating installation directory..."
INSTALL_DIR="/opt/newrelic"
sudo mkdir -p "$INSTALL_DIR"

# Download agent
echo "Downloading infrastructure agent..."
AGENT_URL="https://download.newrelic.com/infrastructure_agent/linux/amd64/newrelic-infra_linux_amd64.tar.gz"
sudo curl -L "$AGENT_URL" -o "$INSTALL_DIR/newrelic-infra.tar.gz"

# Extract agent
echo "Extracting agent..."
sudo tar -xzf "$INSTALL_DIR/newrelic-infra.tar.gz" -C "$INSTALL_DIR"

# Configure agent
echo "Configuring agent..."
cat > "$INSTALL_DIR/newrelic-infra/newrelic-infra.yml" << EOF
license_key: 
host: 
port: 
log_level: 
EOF

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/newrelic-infra.service << EOF
[Unit]
Description=New Relic Infrastructure Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=$INSTALL_DIR/newrelic-infra/newrelic-infra
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
echo "Starting infrastructure agent service..."
sudo systemctl daemon-reload
sudo systemctl enable newrelic-infra
sudo systemctl start newrelic-infra

# Verify installation
echo "Verifying installation..."
if ! sudo systemctl is-active --quiet newrelic-infra; then
    echo "Error: Infrastructure agent service is not running"
    exit 1
fi

echo "Infrastructure agent installation completed successfully" 