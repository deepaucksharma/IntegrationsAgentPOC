# src/workflow_agent/integrations/handlers/aws.py
import logging
from typing import Dict, Any, Optional, List
from ...core.state import WorkflowState
from ..base import IntegrationBase

logger = logging.getLogger(__name__)

class AwsIntegration(IntegrationBase):
    """Integration handler for AWS."""
    
    async def handle(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle AWS integration."""
        logger.info(f"Handling AWS integration for {state.target_name} with action {state.action}")
        
        # Check for required parameters
        if not state.parameters.get("aws_access_key"):
            return {"error": "Missing required parameter: aws_access_key"}
        
        if not state.parameters.get("aws_secret_key"):
            return {"error": "Missing required parameter: aws_secret_key"}
        
        if state.action == "install":
            script = f"""#!/usr/bin/env bash
set -e
echo "Installing AWS integration"

# Install AWS CLI if needed
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI..."
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y awscli
    elif command -v yum &> /dev/null; then
        yum install -y awscli
    else
        echo "Installing AWS CLI using pip..."
        pip install awscli
    fi
fi

# Configure AWS credentials
mkdir -p ~/.aws
cat > ~/.aws/credentials <<EOF
[default]
aws_access_key_id = {state.parameters.get('aws_access_key')}
aws_secret_access_key = {state.parameters.get('aws_secret_key')}
EOF

# Configure monitoring agent for AWS
mkdir -p /etc/newrelic-infra/integrations.d/
cat > /etc/newrelic-infra/integrations.d/aws-config.yml <<EOF
integrations:
  - name: nri-aws
    config:
      aws:
        access_key: {state.parameters.get('aws_access_key')}
        secret_key: {state.parameters.get('aws_secret_key')}
        regions:
          - us-east-1
          - us-west-1
EOF

# Restart agent to apply configuration
if systemctl is-active --quiet newrelic-infra; then
    systemctl restart newrelic-infra
fi

echo "AWS integration installed successfully"
"""
            return {
                "script": script,
                "source": "aws_integration"
            }
        elif state.action == "remove":
            script = f"""#!/usr/bin/env bash
set -e
echo "Removing AWS integration"

# Remove AWS integration configuration
if [ -f "/etc/newrelic-infra/integrations.d/aws-config.yml" ]; then
    rm -f /etc/newrelic-infra/integrations.d/aws-config.yml
    echo "Removed AWS integration configuration"
fi

# Restart agent to apply changes
if systemctl is-active --quiet newrelic-infra; then
    systemctl restart newrelic-infra
fi

echo "AWS integration removed successfully"
"""
            return {
                "script": script,
                "source": "aws_integration"
            }
        else:
            return {
                "error": f"Unsupported action '{state.action}' for AWS integration"
            }