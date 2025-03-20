#!/bin/bash

# Error handling
set -e
trap 'echo "Error on line $LINENO"' ERR

# Logging
LOG_FILE="/var/log/custom_integration_install.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "Starting custom integration installation..."

# Verify prerequisites
echo "Verifying prerequisites..."
if ! command -v curl &> /dev/null; then
    echo "Error: curl is required but not installed"
    exit 1
fi

# Create installation directory
echo "Creating installation directory..."
INSTALL_DIR="/opt/custom-integration"
sudo mkdir -p "$INSTALL_DIR"

# Download integration
echo "Downloading custom integration..."
INTEGRATION_URL="https://example.com/custom-integration"
sudo curl -L "$INTEGRATION_URL" -o "$INSTALL_DIR/custom-integration.tar.gz"

# Extract integration
echo "Extracting integration..."
sudo tar -xzf "$INSTALL_DIR/custom-integration.tar.gz" -C "$INSTALL_DIR"

# Configure integration
echo "Configuring integration..."
CONFIG_DIR="/etc/newrelic-infra/integrations.d/"
sudo mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_DIR/custom-integration-config.yml" << EOF
integration_name: custom-integration
version: 1.0.0
settings:
  enabled: true
  log_level: info
EOF

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/custom-integration.service << EOF
[Unit]
Description=Custom Integration Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=$INSTALL_DIR/custom-integration/custom-integration
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
echo "Starting custom integration service..."
sudo systemctl daemon-reload
sudo systemctl enable custom-integration
sudo systemctl start custom-integration

# Verify installation
echo "Verifying installation..."
if ! sudo systemctl is-active --quiet custom-integration; then
    echo "Error: Custom integration service is not running"
    exit 1
fi

echo "Custom integration installation completed successfully" 