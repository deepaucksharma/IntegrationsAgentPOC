import os
import sys
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# Path to templates
template_dir = Path(__file__).parent / 'templates'
env = Environment(loader=FileSystemLoader(template_dir))

# Load template
template = env.get_template('install/infra_agent.ps1.j2')

# Define parameters
params = {
    "license_key": "YOUR_LICENSE_KEY",
    "host": "localhost",
    "port": "8080",
    "install_dir": r"C:\Program Files\New Relic",
    "config_path": r"C:\ProgramData\New Relic",
    "log_path": r"C:\ProgramData\New Relic\logs"
}

# Context for template
context = {
    'action': 'install',
    'target_name': 'infrastructure-agent',
    'integration_type': 'infra_agent',
    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    'parameters': params  # Pass params as parameters dict
}

# Render template
rendered = template.render(**context)

# Write to file
output_file = Path(__file__).parent / 'test_output.ps1'
with open(output_file, 'w') as f:
    f.write(rendered)

print(f"Template rendered to {output_file}")
