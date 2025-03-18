"""Module for building dynamic verification scripts."""
from typing import Dict, Any, List, Optional
import logging
import os
from string import Template

logger = logging.getLogger(__name__)

class DynamicVerificationBuilder:
    """Builds verification scripts from documentation and generic checks."""
    
    def __init__(self):
        """Initialize the verification builder with template mappings."""
        self.verification_templates = {
            "windows": {
                "header": """# Windows verification script
Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = "Stop"
""",
                "service_check": Template("""
# Check if service $service_name is running
$service = Get-Service -Name "$service_name" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "Service $service_name is running"
} else {
    Write-Error "Service $service_name is not running"
    exit 1
}
"""),
                "port_check": Template("""
# Check if port $port is listening
$listening = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue
if ($listening.TcpTestSucceeded) {
    Write-Host "Port $port is listening"
} else {
    Write-Error "Port $port is not listening"
    exit 1
}
"""),
                "process_check": Template("""
# Check if process $process_name is running
$process = Get-Process "$process_name" -ErrorAction SilentlyContinue
if ($process) {
    Write-Host "Process $process_name is running"
} else {
    Write-Error "Process $process_name is not running"
    exit 1
}
""")
            },
            "linux": {
                "header": """#!/bin/bash
set -e

# Error handler
trap 'handle_error $? $LINENO' ERR

handle_error() {
    echo "Error $1 occurred on line $2"
    exit 1
}
""",
                "service_check": Template("""
# Check if service $service_name is running
if systemctl is-active --quiet $service_name; then
    echo "Service $service_name is running"
else
    echo "Service $service_name is not running"
    exit 1
fi
"""),
                "port_check": Template("""
# Check if port $port is listening
if netstat -tuln | grep ":$port\\s" > /dev/null; then
    echo "Port $port is listening"
else
    echo "Port $port is not listening"
    exit 1
fi
"""),
                "process_check": Template("""
# Check if process $process_name is running
if pgrep -f "$process_name" > /dev/null; then
    echo "Process $process_name is running"
else
    echo "Process $process_name is not running"
    exit 1
fi
""")
            }
        }

    async def build_verification_script(self, state: Any) -> str:
        """Creates a verification script for the integration.
        
        Args:
            state: Current workflow state with documentation
            
        Returns:
            Generated verification script
            
        Raises:
            Exception: If script generation fails
        """
        try:
            logger.info("Building verification script")
            
            # Get platform-specific information
            platform_info = state.template_data.get("platform_info", {})
            system = platform_info.get("system", "").lower()
            
            # Get verification steps and configuration
            verify_steps = state.template_data.get("docs", {}).get("verification_steps", [])
            config = state.template_data.get("docs", {}).get("configuration_options", {})
            
            # Generate the script
            script_lines = []
            
            # Add appropriate header
            script_lines.extend(self._generate_header(system))
            
            # Add custom verification steps
            script_lines.extend(self._generate_custom_checks(system, verify_steps))
            
            # Add generic checks based on integration type
            script_lines.extend(self._generate_generic_checks(system, state))
            
            # Add configuration validation
            script_lines.extend(self._generate_config_validation(system, config))
            
            script = "\n".join(script_lines)
            
            logger.info("Successfully built verification script")
            return script
            
        except Exception as e:
            logger.error(f"Failed to build verification script: {e}")
            raise

    def _generate_header(self, system: str) -> List[str]:
        """Generates script header with appropriate shell and error handling.
        
        Args:
            system: Target operating system
            
        Returns:
            List of script lines for header
        """
        templates = self.verification_templates.get(system, self.verification_templates["linux"])
        return [templates["header"]]

    def _generate_custom_checks(self, system: str, verify_steps: List[str]) -> List[str]:
        """Generates custom verification checks from documentation.
        
        Args:
            system: Target operating system
            verify_steps: List of verification steps
            
        Returns:
            List of script lines for custom checks
        """
        check_lines = ["\n# Custom verification checks"]
        
        for step in verify_steps:
            # Clean and format the verification command
            cleaned_step = self._clean_verification_step(step)
            if cleaned_step:
                check_lines.extend([
                    f"\necho 'Running verification: {cleaned_step}'",
                    cleaned_step,
                    'if [ $? -ne 0 ]; then',
                    '    echo "Verification failed"',
                    '    exit 1',
                    'fi' if system == "linux" else ''
                ])
        
        return check_lines

    def _generate_generic_checks(self, system: str, state: Any) -> List[str]:
        """Generates generic verification checks based on integration type.
        
        Args:
            system: Target operating system
            state: Current workflow state
            
        Returns:
            List of script lines for generic checks
        """
        templates = self.verification_templates.get(system, self.verification_templates["linux"])
        check_lines = ["\n# Generic verification checks"]
        
        # Extract integration details
        integration_type = state.integration_type.lower()
        
        # Add service check if applicable
        if "agent" in integration_type or "service" in integration_type:
            service_name = f"newrelic-{integration_type}"
            check_lines.append(templates["service_check"].substitute(service_name=service_name))
        
        # Add process check
        process_name = f"newrelic-{integration_type}"
        check_lines.append(templates["process_check"].substitute(process_name=process_name))
        
        # Add common port checks
        common_ports = self._get_common_ports(integration_type)
        for port in common_ports:
            check_lines.append(templates["port_check"].substitute(port=port))
        
        return check_lines

    def _generate_config_validation(self, system: str, config: Dict[str, str]) -> List[str]:
        """Generates configuration validation checks.
        
        Args:
            system: Target operating system
            config: Configuration options dictionary
            
        Returns:
            List of script lines for config validation
        """
        validate_lines = ["\n# Configuration validation"]
        
        for option, requirement in config.items():
            if requirement == "required":
                if system == "windows":
                    validate_lines.extend([
                        f'if (-not (Test-Path env:{option})) {{',
                        f'    Write-Error "Required configuration {option} is not set"',
                        '    exit 1',
                        '}'
                    ])
                else:
                    validate_lines.extend([
                        f'if [ -z "${{${option}}}" ]; then',
                        f'    echo "Required configuration {option} is not set"',
                        '    exit 1',
                        'fi'
                    ])
        
        return validate_lines

    def _clean_verification_step(self, step: str) -> str:
        """Cleans and formats a verification step command.
        
        Args:
            step: Raw verification step
            
        Returns:
            Cleaned command string
        """
        # Remove common documentation artifacts
        step = step.strip()
        step = step.replace("```", "").replace("`", "")
        step = step.replace("$ ", "").replace("# ", "")
        
        # Remove explanatory text in parentheses
        while "(" in step and ")" in step:
            start = step.find("(")
            end = step.find(")") + 1
            step = step[:start].strip() + step[end:].strip()
        
        return step

    def _get_common_ports(self, integration_type: str) -> List[int]:
        """Gets common ports for an integration type.
        
        Args:
            integration_type: Type of integration
            
        Returns:
            List of common ports
        """
        # Define common ports for different integration types
        port_mappings = {
            "mysql": [3306],
            "postgresql": [5432],
            "redis": [6379],
            "mongodb": [27017],
            "elasticsearch": [9200, 9300],
            "nginx": [80, 443],
            "apache": [80, 443],
            "kafka": [9092],
            "rabbitmq": [5672, 15672],
            "default": [8080]
        }
        
        # Return ports for the integration type or default ports
        return port_mappings.get(integration_type, port_mappings["default"]) 