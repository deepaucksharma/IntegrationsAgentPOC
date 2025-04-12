# Templates Directory

This directory contains Jinja2 templates for generating scripts and configuration files for various integrations.

## Directory Structure

Templates are organized by action type and integration:

```
templates/
├── install/                 # Installation templates
│   ├── infra_agent.ps1.j2   # Windows PowerShell template for infra_agent
│   ├── infra_agent.sh.j2    # Linux/Unix shell template for infra_agent
│   └── ...
├── verify/                  # Verification templates
│   ├── infra_agent.ps1.j2
│   └── ...
├── uninstall/               # Uninstallation templates
│   ├── infra_agent.ps1.j2
│   └── ...
└── common/                  # Common templates and includes
    ├── header.j2
    ├── footer.j2
    └── ...
```

## Template Guidelines

When creating templates:

1. Use **descriptive variable names** - e.g., `{{ install_dir }}` not `{{ dir }}`
2. Include **error handling** in scripts
3. Add **comments** to explain complex sections
4. Use **conditional logic** for different OS variants
5. Report changes with `CHANGE_JSON_BEGIN` and `CHANGE_JSON_END` markers for change tracking
6. Include **logging** statements

## Example Template

```jinja
#!/bin/bash
# {{ integration_type }} installation for {{ target_name }}
# Generated on {{ timestamp }}

# Error handling
set -e

# Create installation directory
mkdir -p "{{ install_dir }}"
echo "Created installation directory: {{ install_dir }}"

# Report change for tracking
echo "CHANGE_JSON_BEGIN"
echo '{
  "type": "directory_created",
  "target": "{{ install_dir }}",
  "revertible": true,
  "revert_command": "rm -rf \"{{ install_dir }}\""
}'
echo "CHANGE_JSON_END"

# Download and install package
{% if package_url %}
echo "Downloading package from {{ package_url }}..."
curl -sSL "{{ package_url }}" -o "{{ install_dir }}/package.tar.gz"
tar -xzf "{{ install_dir }}/package.tar.gz" -C "{{ install_dir }}"
rm "{{ install_dir }}/package.tar.gz"
{% else %}
echo "No package URL provided, using default installation method"
# Default installation code here
{% endif %}

# Configure the integration
cat > "{{ config_path }}/config.json" << EOF
{
  "license_key": "{{ license_key }}",
  "host": "{{ host }}",
  "port": "{{ port }}",
  "log_level": "INFO"
}
EOF

echo "{{ integration_type }} installation completed successfully"
exit 0
```

## Using the Template Utilities

Instead of using Jinja2 directly, use the centralized template utilities:

```python
from workflow_agent.templates.utils import render_template

# Render a template
rendered = render_template("install/infra_agent.ps1.j2", context)

# Or use the template utility class for more options
from workflow_agent.templates.utils import TemplateUtils
template_utils = TemplateUtils()
rendered = template_utils.render_template("install/infra_agent.ps1.j2", context)
```

## Testing Templates

To test a template:

1. Create a test context file (JSON or YAML)
2. Render the template with the test context
3. Verify the output script works as expected

Example test script:

```python
import json
from workflow_agent.templates.utils import render_template

# Test context
context = {
    "integration_type": "test_integration",
    "target_name": "test-service",
    "install_dir": "/tmp/test_integration",
    "config_path": "/tmp/test_integration/config",
    "license_key": "test-key",
    "host": "localhost",
    "port": "8080",
    "timestamp": "2025-04-10 12:00:00"
}

# Render template
rendered = render_template("install/infra_agent.sh.j2", context)

# Write to file for testing
with open("test_script.sh", "w") as f:
    f.write(rendered)
    
print("Test script generated at: test_script.sh")
```
