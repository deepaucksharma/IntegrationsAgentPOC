"""Infrastructure monitoring agent integration."""
import logging
from typing import Dict, Any, List, Optional

from ...core.state import WorkflowState
from ..base import IntegrationBase

logger = logging.getLogger(__name__)

class InfraAgentIntegration(IntegrationBase):
    """Integration handler for infrastructure monitoring agent."""
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        return ["monitoring_agent", "infra_agent", "metrics_agent"]
    
    @classmethod
    def get_category(cls) -> str:
        return "monitoring"
    
    @classmethod
    def get_parameters(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "license_key": {
                "type": "string",
                "description": "License key for the monitoring service",
                "required": True
            },
            "api_key": {
                "type": "string",
                "description": "API key for the monitoring service",
                "required": False
            },
            "endpoint": {
                "type": "string",
                "description": "Endpoint URL for the monitoring service",
                "required": False,
                "default": "https://metrics-api.newrelic.com"
            }
        }
    
    async def handle(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        validation_result = await self.validate(state)
        if not validation_result.get("valid", False):
            return {"error": validation_result.get("error", "Parameter validation failed")}
        
        if state.action == "install":
            script = f"""#!/usr/bin/env bash
set -e
echo "Installing monitoring agent"

# Determine system type
if [ -f /etc/debian_version ]; then
    echo "Detected Debian/Ubuntu system"
    curl -fsSL https://monitoring-agent-repo.example.com/gpg | apt-key add -
    echo "deb https://monitoring-agent-repo.example.com/apt stable main" | tee /etc/apt/sources.list.d/monitoring-agent.list
    apt-get update
    apt-get install -y monitoring-agent
elif [ -f /etc/redhat-release ]; then
    echo "Detected RHEL/CentOS system"
    curl -fsSL https://monitoring-agent-repo.example.com/yum/monitoring-agent.repo > /etc/yum.repos.d/monitoring-agent.repo
    yum install -y monitoring-agent
else
    echo "Unsupported operating system"
    exit 1
fi

mkdir -p /etc/monitoring-agent/
cat > /etc/monitoring-agent/agent.yaml << EOF
license_key: {state.parameters.get('license_key')}
endpoint: {state.parameters.get('endpoint', 'https://metrics-api.newrelic.com')}
EOF

systemctl enable monitoring-agent
systemctl start monitoring-agent

echo "Monitoring agent installed successfully"
"""
            return {
                "script": script,
                "source": "infra_agent_integration"
            }
        elif state.action == "remove":
            script = f"""#!/usr/bin/env bash
set -e
echo "Removing monitoring agent"

systemctl stop monitoring-agent || true
systemctl disable monitoring-agent || true

if [ -f /etc/debian_version ]; then
    echo "Detected Debian/Ubuntu system"
    apt-get remove -y monitoring-agent
    rm -f /etc/apt/sources.list.d/monitoring-agent.list
elif [ -f /etc/redhat-release ]; then
    echo "Detected RHEL/CentOS system"
    yum remove -y monitoring-agent
    rm -f /etc/yum.repos.d/monitoring-agent.repo
else
    echo "Unsupported operating system"
    exit 1
fi

rm -rf /etc/monitoring-agent/

echo "Monitoring agent removed successfully"
"""
            return {
                "script": script,
                "source": "infra_agent_integration"
            }
        elif state.action == "verify":
            script = f"""#!/usr/bin/env bash
set -e
echo "Verifying monitoring agent"

if ! command -v monitoring-agent &> /dev/null; then
    echo "Error: monitoring-agent is not installed"
    exit 1
fi

if ! systemctl is-active --quiet monitoring-agent; then
    echo "Error: monitoring-agent is not running"
    exit 1
fi

if [ ! -f /etc/monitoring-agent/agent.yaml ]; then
    echo "Error: monitoring-agent configuration not found"
    exit 1
fi

echo "Monitoring agent is installed and running"
"""
            return {
                "script": script,
                "source": "infra_agent_integration"
            }
        else:
            return {
                "error": f"Unsupported action '{state.action}' for infrastructure agent integration"
            }