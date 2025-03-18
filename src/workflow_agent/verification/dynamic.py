"""Dynamic verification script builder."""
from typing import Dict, Any, List
import logging
from string import Template
import re

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
"""),
                "file_check": Template("""
# Check if file $file_path exists
if (Test-Path "$file_path") {
    Write-Host "File $file_path exists"
} else {
    Write-Error "File $file_path not found"
    exit 1
}
"""),
                "config_check": Template("""
# Check if configuration contains $search_string
$content = Get-Content "$file_path" -ErrorAction SilentlyContinue
if ($content -match "$search_string") {
    Write-Host "Configuration check passed: $search_string found in $file_path"
} else {
    Write-Error "Configuration check failed: $search_string not found in $file_path"
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
if systemctl is-active --quiet $service_name 2>/dev/null || service $service_name status >/dev/null 2>&1; then
    echo "Service $service_name is running"
else
    echo "Service $service_name is not running"
    exit 1
fi
"""),
                "port_check": Template("""
# Check if port $port is listening
if command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep -q ":$port\\s"; then
        echo "Port $port is listening"
    else
        echo "Port $port is not listening"
        exit 1
    fi
elif command -v ss >/dev/null 2>&1; then
    if ss -tuln | grep -q ":$port\\s"; then
        echo "Port $port is listening"
    else
        echo "Port $port is not listening"
        exit 1
    fi
else
    echo "Cannot check port $port: netstat/ss commands not available"
    exit 1
fi
"""),
                "process_check": Template("""
# Check if process $process_name is running
if pgrep -f "$process_name" >/dev/null; then
    echo "Process $process_name is running"
else
    echo "Process $process_name is not running"
    exit 1
fi
"""),
                "file_check": Template("""
# Check if file $file_path exists
if [ -f "$file_path" ]; then
    echo "File $file_path exists"
else
    echo "File $file_path not found"
    exit 1
fi
"""),
                "config_check": Template("""
# Check if configuration contains $search_string
if grep -q "$search_string" "$file_path" 2>/dev/null; then
    echo "Configuration check passed: $search_string found in $file_path"
else
    echo "Configuration check failed: $search_string not found in $file_path"
    exit 1
fi
""")
            }
        }

    async def build_verification_script(self, state: Any) -> str:
        """Creates a verification script for the integration."""
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
            
            # Add custom verification steps from documentation
            script_lines.extend(self._generate_custom_checks(system, verify_steps, state))
            
            # Add generic checks based on integration type
            script_lines.extend(self._generate_generic_checks(system, state))
            
            # Add configuration validation
            script_lines.extend(self._generate_config_validation(system, config, state))
            
            # Add final success message
            script_lines.append('\necho "All verification checks passed successfully"')
            
            script = "\n".join(script_lines)
            
            logger.info("Successfully built verification script")
            return script
            
        except Exception as e:
            logger.error(f"Failed to build verification script: {e}")
            raise

    def _generate_header(self, system: str) -> List[str]:
        """Generates script header with appropriate shell and error handling."""
        templates = self.verification_templates.get(system, self.verification_templates["linux"])
        return [templates["header"]]

    def _generate_custom_checks(self, system: str, verify_steps: List[str], state: Any) -> List[str]:
        """Generates custom verification checks from documentation."""
        templates = self.verification_templates.get(system, self.verification_templates["linux"])
        check_lines = ["\n# Custom verification checks"]
        
        for step in verify_steps:
            # Try to intelligently determine what type of check this is
            file_match = re.search(r'check (?:if|that|for) (file|directory) ["\']?([^\s"\']+)', step.lower())
            service_match = re.search(r'check (?:if|that|for) service ["\']?([^\s"\']+)', step.lower())
            process_match = re.search(r'check (?:if|that|for) process ["\']?([^\s"\']+)', step.lower())
            port_match = re.search(r'check (?:if|that|for) port ["\']?(\d+)', step.lower())
            config_match = re.search(r'(?:check|verify) (?:if|that|for) ([^\s]+) (?:in|contains) ([^\s]+)', step.lower())
            
            if file_match:
                file_type, file_path = file_match.groups()
                if file_type == "file":
                    check_lines.append(templates["file_check"].substitute(file_path=file_path))
                else:  # directory
                    if system == "windows":
                        check_lines.append(f'if (Test-Path "{file_path}" -PathType Container) {{ Write-Host "Directory {file_path} exists" }} else {{ Write-Error "Directory {file_path} not found"; exit 1 }}')
                    else:
                        check_lines.append(f'if [ -d "{file_path}" ]; then echo "Directory {file_path} exists"; else echo "Directory {file_path} not found"; exit 1; fi')
            elif service_match:
                service_name = service_match.group(1)
                check_lines.append(templates["service_check"].substitute(service_name=service_name))
            elif process_match:
                process_name = process_match.group(1)
                check_lines.append(templates["process_check"].substitute(process_name=process_name))
            elif port_match:
                port = port_match.group(1)
                check_lines.append(templates["port_check"].substitute(port=port))
            elif config_match:
                search_string, file_path = config_match.groups()
                check_lines.append(templates["config_check"].substitute(search_string=search_string, file_path=file_path))
            else:
                # Just add as a custom command if we can't categorize it
                cmd = self._clean_verification_step(step)
                if cmd:
                    check_lines.extend([
                        f"\necho 'Running verification: {cmd}'",
                        cmd,
                        'if [ $? -ne 0 ]; then' if system == "linux" else 'if ($LASTEXITCODE -ne 0) {',
                        '    echo "Verification failed"' if system == "linux" else '    Write-Error "Verification failed"',
                        '    exit 1' if system == "linux" else '    exit 1',
                        'fi' if system == "linux" else '}'
                    ])
        
        return check_lines

    def _generate_generic_checks(self, system: str, state: Any) -> List[str]:
        """Generates generic verification checks based on integration type."""
        templates = self.verification_templates.get(system, self.verification_templates["linux"])
        check_lines = ["\n# Generic verification checks"]
        
        # Extract integration details
        integration_type = state.integration_type.lower()
        integration_name = state.target_name.lower()
        
        # Common New Relic paths to check
        if system == "linux":
            check_lines.append(templates["file_check"].substitute(
                file_path=f"/etc/newrelic-infra/integrations.d/{integration_name}-config.yml"
            ))
        elif system == "windows":
            check_lines.append(templates["file_check"].substitute(
                file_path=f"C:\\Program Files\\New Relic\\newrelic-infra\\integrations.d\\{integration_name}-config.yml"
            ))
        
        # Add service check if applicable
        if "agent" in integration_type or "service" in integration_type:
            service_name = f"newrelic-{integration_type}"
            check_lines.append(templates["service_check"].substitute(service_name=service_name))
        
        # Add process check
        process_name = f"newrelic-{integration_type}"
        check_lines.append(templates["process_check"].substitute(process_name=process_name))
        
        # Add common port checks
        common_ports = self._get_common_ports(integration_type)
        check_lines.extend([templates["port_check"].substitute(port=port) for port in common_ports])
        
        return check_lines

    def _get_common_ports(self, integration_type: str) -> List[int]:
        """Gets common ports for an integration type."""
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
        for key, ports in port_mappings.items():
            if key in integration_type:
                return ports
        return port_mappings["default"]

    def _generate_config_validation(self, system: str, config: Dict[str, str], state: Any) -> List[str]:
        """Generates configuration validation checks."""
        templates = self.verification_templates.get(system, self.verification_templates["linux"])
        validate_lines = ["\n# Configuration validation"]
        
        # Files to check for configuration
        config_files = []
        if system == "linux":
            config_files = [f"/etc/newrelic-infra/integrations.d/{state.target_name.lower()}-config.yml"]
        elif system == "windows":
            config_files = [f"C:\\Program Files\\New Relic\\newrelic-infra\\integrations.d\\{state.target_name.lower()}-config.yml"]
        
        # Check for required configuration options
        for option, requirement in config.items():
            if requirement == "required":
                for file_path in config_files:
                    validate_lines.append(templates["config_check"].substitute(
                        search_string=option,
                        file_path=file_path
                    ))
        
        return validate_lines

    def _clean_verification_step(self, step: str) -> str:
        """Cleans and formats a verification step command."""
        # Remove common documentation artifacts
        step = step.strip()
        step = step.replace("```", "").replace("`", "")
        step = step.replace("$ ", "").replace("# ", "")
        
        # Remove explanatory text in parentheses
        import re
        step = re.sub(r'\([^)]*\)', '', step)
        
        return step