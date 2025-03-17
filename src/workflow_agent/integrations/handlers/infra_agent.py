# src/workflow_agent/integrations/handlers/infra_agent.py
import logging
from typing import Dict, Any, Optional, List
from ...core.state import WorkflowState
from ..base import IntegrationBase

logger = logging.getLogger(__name__)

class InfraAgentIntegration(IntegrationBase):
    """Integration handler for infrastructure agents."""
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        return ["postgres", "mysql", "redis", "nginx", "apache"]
    
    async def handle(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle infrastructure agent integration."""
        logger.info(f"Handling infra agent integration for {state.target_name}")
        
        # Specific handling based on target and action
        if state.target_name == "postgres":
            return await self._handle_postgres(state, config)
        elif state.target_name == "mysql":
            return await self._handle_mysql(state, config)
        else:
            # Generic handling
            script = f"""#!/usr/bin/env bash
set -e
echo "Handling infrastructure agent integration for {state.target_name}"
echo "Action: {state.action}"

# Check for required tools
if ! command -v curl &> /dev/null; then
    echo "Error: curl is required but not installed"
    exit 1
fi

# Create a directory for configuration if needed
mkdir -p /etc/{state.target_name}-agent

# Write configuration
cat > /etc/{state.target_name}-agent/config.yml <<EOF
integration:
  name: {state.target_name}
  action: {state.action}
EOF

echo "Configuration created for {state.target_name}"
"""
            return {
                "script": script,
                "source": "integration_handler"
            }
    
    async def _handle_postgres(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle Postgres-specific integration."""
        if state.action == "install":
            script = f"""#!/usr/bin/env bash
set -e
echo "Installing PostgreSQL monitoring agent"

# Validate parameters
if [ -z "{state.parameters.get('db_host', '')}" ]; then
    echo "Error: db_host parameter is required"
    exit 1
fi

if [ -z "{state.parameters.get('db_port', '')}" ]; then
    echo "Error: db_port parameter is required"
    exit 1
fi

# Check if PostgreSQL is reachable
if ! pg_isready -h {state.parameters.get('db_host')} -p {state.parameters.get('db_port')}; then
    echo "Warning: PostgreSQL not reachable at {state.parameters.get('db_host')}:{state.parameters.get('db_port')}"
fi

# Install required packages
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y postgresql-client
elif command -v yum &> /dev/null; then
    yum install -y postgresql
else
    echo "Warning: Unsupported package manager"
fi

# Configure monitoring agent
mkdir -p /etc/newrelic-infra/integrations.d/
cat > /etc/newrelic-infra/integrations.d/postgres-config.yml <<EOF
integration_name: com.newrelic.postgresql
instances:
  - name: postgres-instance
    command: all_data
    arguments:
      host: {state.parameters.get('db_host')}
      port: {state.parameters.get('db_port')}
EOF

echo "Postgres agent configuration complete"
echo "Testing connection to database..."
psql -h {state.parameters.get('db_host')} -p {state.parameters.get('db_port')} -c "SELECT version();"

# Restart agent to apply configuration
if systemctl is-active --quiet newrelic-infra; then
    systemctl restart newrelic-infra
fi

echo "PostgreSQL monitoring agent installed successfully"
"""
            return {
                "script": script,
                "source": "postgres_integration"
            }
        elif state.action == "remove":
            script = f"""#!/usr/bin/env bash
set -e
echo "Removing PostgreSQL monitoring agent configuration"

# Remove configuration file
if [ -f "/etc/newrelic-infra/integrations.d/postgres-config.yml" ]; then
    rm -f /etc/newrelic-infra/integrations.d/postgres-config.yml
    echo "Removed postgres-config.yml"
fi

# Restart agent to apply changes
if systemctl is-active --quiet newrelic-infra; then
    systemctl restart newrelic-infra
    echo "Restarted newrelic-infra service"
fi

echo "PostgreSQL monitoring agent removed successfully"
"""
            return {
                "script": script,
                "source": "postgres_integration"
            }
        else:
            return {
                "error": f"Unsupported action '{state.action}' for postgres integration"
            }
    
    async def _handle_mysql(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle MySQL-specific integration."""
        # Implementation similar to _handle_postgres but for MySQL
        if state.action == "install":
            script = f"""#!/usr/bin/env bash
set -e
echo "Installing MySQL monitoring agent"

# Validate parameters
if [ -z "{state.parameters.get('db_host', '')}" ]; then
    echo "Error: db_host parameter is required"
    exit 1
fi

if [ -z "{state.parameters.get('db_port', '')}" ]; then
    echo "Error: db_port parameter is required"
    exit 1
fi

# Check if MySQL client is installed
if ! command -v mysql &> /dev/null; then
    echo "Installing MySQL client..."
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y mysql-client
    elif command -v yum &> /dev/null; then
        yum install -y mysql
    else
        echo "Warning: Unsupported package manager"
    fi
fi

# Configure monitoring agent
mkdir -p /etc/newrelic-infra/integrations.d/
cat > /etc/newrelic-infra/integrations.d/mysql-config.yml <<EOF
integration_name: com.newrelic.mysql
instances:
  - name: mysql-instance
    command: all_data
    arguments:
      hostname: {state.parameters.get('db_host')}
      port: {state.parameters.get('db_port')}
EOF

echo "MySQL agent configuration complete"
echo "Testing connection to MySQL server..."
mysql -h {state.parameters.get('db_host')} -P {state.parameters.get('db_port')} -e "SELECT VERSION();"

# Restart agent to apply configuration
if systemctl is-active --quiet newrelic-infra; then
    systemctl restart newrelic-infra
fi

echo "MySQL monitoring agent installed successfully"
"""
            return {
                "script": script,
                "source": "mysql_integration"
            }
        elif state.action == "remove":
            script = f"""#!/usr/bin/env bash
set -e
echo "Removing MySQL monitoring agent configuration"

# Remove configuration file
if [ -f "/etc/newrelic-infra/integrations.d/mysql-config.yml" ]; then
    rm -f /etc/newrelic-infra/integrations.d/mysql-config.yml
    echo "Removed mysql-config.yml"
fi

# Restart agent to apply changes
if systemctl is-active --quiet newrelic-infra; then
    systemctl restart newrelic-infra
    echo "Restarted newrelic-infra service"
fi

echo "MySQL monitoring agent removed successfully"
"""
            return {
                "script": script,
                "source": "mysql_integration"
            }
        else:
            return {
                "error": f"Unsupported action '{state.action}' for mysql integration"
            }