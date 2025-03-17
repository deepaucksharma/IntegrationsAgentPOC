import logging
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Callable, Awaitable
from .state import WorkflowState
from .configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

class IntegrationBase:
    """Base class for all integration handlers."""
    
    @classmethod
    def get_name(cls) -> str:
        """Get the name of this integration."""
        return cls.__name__.lower().replace("integration", "")
    
    @classmethod
    def get_supported_targets(cls) -> List[str]:
        """Return list of targets this integration supports."""
        return []
    
    async def handle(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle the integration request.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state
        """
        logger.info(f"Base implementation for {self.get_name()} integration")
        return {}

class IntegrationRegistry:
    """Registry for integration handlers."""
    
    _integrations: Dict[str, Type[IntegrationBase]] = {}
    
    @classmethod
    def register(cls, integration_class: Type[IntegrationBase]) -> None:
        """
        Register an integration handler.
        
        Args:
            integration_class: Class that implements IntegrationBase
        """
        name = integration_class.get_name()
        cls._integrations[name] = integration_class
        logger.debug(f"Registered integration handler: {name}")
    
    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        """
        Get integration handler by name.
        
        Args:
            name: Name of the integration
            
        Returns:
            Integration class or None if not found
        """
        return cls._integrations.get(name.lower())
    
    @classmethod
    def list_integrations(cls) -> List[str]:
        """
        Get list of available integrations.
        
        Returns:
            List of integration names
        """
        return list(cls._integrations.keys())
    
    @classmethod
    def discover_integrations(cls, package_path: str = None) -> None:
        """
        Discover and register integration handlers from a package.
        
        Args:
            package_path: Path to package containing integration modules
        """
        if package_path:
            logger.info(f"Discovering integrations in {package_path}")
            try:
                # Load from path
                for finder, name, is_pkg in pkgutil.iter_modules([package_path]):
                    try:
                        module = importlib.import_module(f"{package_path}.{name}")
                        for item_name in dir(module):
                            item = getattr(module, item_name)
                            if (inspect.isclass(item) and 
                                issubclass(item, IntegrationBase) and 
                                item is not IntegrationBase):
                                cls.register(item)
                    except Exception as e:
                        logger.error(f"Error loading integration module {name}: {e}")
            except Exception as e:
                logger.error(f"Error discovering integrations in {package_path}: {e}")


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


class IntegrationHandler:
    """Main handler for all integrations."""
    
    def __init__(self):
        """Initialize the integration handler."""
        # Register built-in integrations
        IntegrationRegistry.register(InfraAgentIntegration)
        IntegrationRegistry.register(AwsIntegration)
        
        # Discover external integrations
        config = ensure_workflow_config()
        for plugin_dir in config.plugin_dirs:
            IntegrationRegistry.discover_integrations(plugin_dir)
    
    async def handle_integration(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle integration request based on integration type.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state
        """
        integration_type = state.integration_type.lower()
        
        # Get integration handler
        integration_class = IntegrationRegistry.get_integration(integration_type)
        if not integration_class:
            logger.warning(f"No integration handler found for {integration_type}, using fallback")
            return {
                "script": f"""#!/usr/bin/env bash
set -e
echo "Handling generic integration for {state.target_name} using {state.integration_type}"
""",
                "source": "fallback_handler"
            }
        
        try:
            integration = integration_class()
            result = await integration.handle(state, config)
            
            # Add default system context if not provided
            if "system_context" not in result:
                from .system_context import get_system_context
                result["system_context"] = get_system_context()
                
            return result
        except Exception as e:
            logger.error(f"Error handling {integration_type} integration: {e}")
            return {"error": f"Integration handler error: {str(e)}"}
    
    async def handle_infra_agent(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Specialized handler for infra agent integrations.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state
        """
        # This is a convenience method that delegates to the InfraAgentIntegration
        state.integration_type = "infra_agent"
        integration = InfraAgentIntegration()
        return await integration.handle(state, config)