import pytest
import os
from workflow_agent.scripting.generator import ScriptGenerator
from workflow_agent.core.state import WorkflowState
from workflow_agent.error.exceptions import ValidationError

@pytest.mark.asyncio
async def test_script_generator_initialization(script_generator: ScriptGenerator):
    """Test script generator initialization."""
    assert script_generator is not None
    assert script_generator.history_manager is not None
    assert script_generator.env is not None

@pytest.mark.asyncio
async def test_script_generator_generate_script(
    script_generator: ScriptGenerator,
    sample_workflow_state: WorkflowState,
    test_config: dict
):
    """Test script generation from template."""
    result = await script_generator.generate_script(sample_workflow_state, test_config)
    assert "script" in result
    assert "changes" in result
    assert "system_context" in result
    assert "nginx" in result["script"]
    assert "1.18.0" in result["script"]

@pytest.mark.asyncio
async def test_script_generator_sanitize_parameters(script_generator: ScriptGenerator):
    """Test parameter sanitization."""
    parameters = {
        "version": "1.18.0",
        "path": "/var/www/html; rm -rf /",
        "ports": ["80", "443; rm -rf /"]
    }
    sanitized = script_generator._sanitize_parameters(parameters)
    assert sanitized["version"] == "1.18.0"
    assert "rm -rf" not in sanitized["path"]
    assert all("rm -rf" not in port for port in sanitized["ports"])

@pytest.mark.asyncio
async def test_script_generator_validate_template(script_generator: ScriptGenerator):
    """Test template validation."""
    # Test valid template
    assert script_generator._validate_template("webserver/nginx-install.sh")
    
    # Test invalid template
    assert not script_generator._validate_template("../../etc/passwd")
    assert not script_generator._validate_template("{{ malicious }}")

@pytest.mark.asyncio
async def test_script_generator_extract_changes(
    script_generator: ScriptGenerator,
    sample_workflow_state: WorkflowState
):
    """Test change extraction from script."""
    script = """
    apt-get update
    apt-get install -y nginx=1.18.0
    systemctl enable nginx
    systemctl start nginx
    """
    changes = await script_generator._extract_changes_from_script(script, sample_workflow_state)
    assert len(changes) > 0
    assert any(change.type == "install" for change in changes)
    assert any(change.type == "configure" for change in changes)

@pytest.mark.asyncio
async def test_script_generator_template_composition(
    script_generator: ScriptGenerator,
    sample_workflow_state: WorkflowState,
    test_config: dict
):
    """Test template composition and inheritance."""
    # Create a base template
    base_template = "tests/fixtures/templates/webserver/base.sh"
    os.makedirs(os.path.dirname(base_template), exist_ok=True)
    
    with open(base_template, "w") as f:
        f.write("""#!/bin/bash
# Base template
set -e
echo "Starting {{ action }} for {{ target_name }}"
{% block content %}{% endblock %}
""")
    
    # Create a derived template
    derived_template = "tests/fixtures/templates/webserver/nginx-install.sh"
    with open(derived_template, "w") as f:
        f.write("""{% extends "webserver/base.sh" %}
{% block content %}
apt-get update
apt-get install -y nginx={{ parameters.version }}
systemctl enable nginx
systemctl start nginx
{% endblock %}
""")
    
    result = await script_generator.generate_script(sample_workflow_state, test_config)
    assert "Starting install for nginx" in result["script"]
    assert "apt-get install" in result["script"]

@pytest.mark.asyncio
async def test_script_generator_error_handling(
    script_generator: ScriptGenerator,
    test_config: dict
):
    """Test error handling in script generation."""
    # Test with invalid template
    state = WorkflowState(
        action="install",
        target_name="invalid_target",
        parameters={"version": "1.18.0"},
        integration_type="infra_agent",
        integration_category="webserver"
    )
    result = await script_generator.generate_script(state, test_config)
    assert "error" in result

@pytest.mark.asyncio
async def test_script_generator_reload_templates(script_generator: ScriptGenerator):
    """Test template reloading."""
    # Create a new template
    new_template = "tests/fixtures/templates/webserver/new-template.sh"
    with open(new_template, "w") as f:
        f.write("echo 'New template'")
    
    # Reload templates
    script_generator.reload_templates()
    
    # Verify the new template is available
    assert script_generator._validate_template("webserver/new-template.sh")

@pytest.mark.asyncio
async def test_script_generator_optimization(
    script_generator: ScriptGenerator,
    sample_workflow_state: WorkflowState,
    test_config: dict
):
    """Test script optimization."""
    # Enable optimization in config
    test_config["configurable"]["use_llm_optimization"] = True
    
    result = await script_generator.generate_script(sample_workflow_state, test_config)
    assert "script" in result
    assert "optimized" in result.get("script_source", "") 