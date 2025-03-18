import logging
from typing import Dict, Any, List
from string import Template

logger = logging.getLogger(__name__)

class DynamicVerificationBuilder:
    """Builds verification scripts based on documentation and generic checks."""
    def __init__(self):
        self.verification_templates = {
            "linux": {
                "header": "#!/bin/bash\nset -e\n",
                "service_check": Template("""
if systemctl is-active --quiet $service_name; then
    echo "Service $service_name is running"
else
    echo "Service $service_name is not running"
    exit 1
fi
"""),
                "port_check": Template("""
if netstat -tuln | grep ":$port\\s" > /dev/null; then
    echo "Port $port is listening"
else
    echo "Port $port is not listening"
    exit 1
fi
"""),
                "process_check": Template("""
if pgrep -f "$process_name" > /dev/null; then
    echo "Process $process_name is running"
else
    echo "Process $process_name is not running"
    exit 1
fi
""")
            },
            "windows": {
                "header": "# Windows verification script\nSet-ExecutionPolicy Bypass -Scope Process -Force\n",
                "service_check": Template("""
$svc = Get-Service -Name "$service_name" -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq "Running") {
    Write-Host "Service $service_name is running"
} else {
    Write-Error "Service $service_name is not running"
    exit 1
}
"""),
                "port_check": Template("""
$listening = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue
if ($listening.TcpTestSucceeded) {
    Write-Host "Port $port is listening"
} else {
    Write-Error "Port $port is not listening"
    exit 1
}
"""),
                "process_check": Template("""
if (Get-Process "$process_name" -ErrorAction SilentlyContinue) {
    Write-Host "Process $process_name is running"
} else {
    Write-Error "Process $process_name is not running"
    exit 1
}
""")
            }
        }

    async def build_verification_script(self, state: Any) -> str:
        try:
            logger.info("Building verification script")
            platform_info = state.template_data.get("platform_info", {})
            system = platform_info.get("system", "linux").lower()
            templates = self.verification_templates.get(system, self.verification_templates["linux"])
            lines = []
            lines.append(templates["header"])
            lines.append("\n# Generic Service Check")
            integration_type = state.integration_type.lower()
            service_name = f"newrelic-{integration_type}"
            lines.append(templates["service_check"].substitute(service_name=service_name))
            lines.append("\n# Generic Process Check")
            process_name = f"newrelic-{integration_type}"
            lines.append(templates["process_check"].substitute(process_name=process_name))
            common_ports = self._get_common_ports(integration_type)
            for port in common_ports:
                lines.append(templates["port_check"].substitute(port=port))
            lines.append('\necho "Verification completed successfully"')
            script = "\n".join(lines)
            logger.info("Verification script built successfully")
            return script
        except Exception as e:
            logger.error(f"Error building verification script: {e}")
            raise

    def _get_common_ports(self, integration_type: str) -> List[int]:
        port_map = {
            "mysql": [3306],
            "default": [8080]
        }
        return port_map.get(integration_type, port_map["default"])