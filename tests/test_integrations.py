"""Test cases for integration implementations."""
import pytest
from pathlib import Path
from workflow_agent.integrations.infra_agent import InfraAgentIntegration
from workflow_agent.integrations.custom import CustomIntegration

@pytest.mark.asyncio
async def test_infra_agent_integration():
    """Test infrastructure agent integration."""
    integration = InfraAgentIntegration()
    
    # Test installation
    install_params = {
        "license_key": "test123",
        "host": "localhost",
        "port": "8080",
        "install_dir": "C:\\Program Files\\Test Agent",
        "config_path": "C:\\ProgramData\\Test Agent\\config",
        "log_path": "C:\\ProgramData\\Test Agent\\logs"
    }
    result = await integration.install(install_params)
    assert result["success"] is True
    assert "details" in result
    assert result["details"]["install_dir"] == install_params["install_dir"]
    
    # Test verification
    verify_params = {
        "install_dir": install_params["install_dir"],
        "config_path": install_params["config_path"],
        "log_path": install_params["log_path"]
    }
    result = await integration.verify(verify_params)
    assert result["success"] is True
    assert result["details"]["status"] == "running"
    
    # Test uninstallation
    uninstall_params = {
        "install_dir": install_params["install_dir"],
        "config_path": install_params["config_path"],
        "log_path": install_params["log_path"]
    }
    result = await integration.uninstall(uninstall_params)
    assert result["success"] is True
    assert "removed_paths" in result["details"]

@pytest.mark.asyncio
async def test_custom_integration():
    """Test custom integration."""
    integration = CustomIntegration()
    
    # Test installation
    install_params = {
        "integration_url": "https://example.com/custom-integration",
        "config_path": "C:\\Program Files\\New Relic\\newrelic-infra\\integrations.d\\"
    }
    result = await integration.install(install_params)
    assert result["success"] is True
    assert "details" in result
    assert result["details"]["url"] == install_params["integration_url"]
    
    # Test verification
    verify_params = {
        "config_path": install_params["config_path"]
    }
    result = await integration.verify(verify_params)
    assert result["success"] is True
    assert result["details"]["status"] == "configured"
    
    # Test uninstallation
    uninstall_params = {
        "config_path": install_params["config_path"]
    }
    result = await integration.uninstall(uninstall_params)
    assert result["success"] is True
    assert "config_path" in result["details"]

@pytest.mark.asyncio
async def test_integration_error_handling():
    """Test error handling in integrations."""
    integration = InfraAgentIntegration()
    
    # Test missing parameters
    with pytest.raises(ValueError):
        await integration.install({})
    
    with pytest.raises(ValueError):
        await integration.verify({})
    
    with pytest.raises(ValueError):
        await integration.uninstall({})

    # Test custom integration error handling
    custom_integration = CustomIntegration()
    
    with pytest.raises(ValueError):
        await custom_integration.install({})
    
    with pytest.raises(ValueError):
        await custom_integration.verify({})
    
    with pytest.raises(ValueError):
        await custom_integration.uninstall({}) 