"""Pytest configuration and fixtures."""
import pytest
import os
from pathlib import Path
from workflow_agent.main import WorkflowAgent
from workflow_agent.config import WorkflowConfiguration

@pytest.fixture
def config():
    """Create a test configuration."""
    return WorkflowConfiguration(
        log_level="INFO",
        use_recovery=True,
        plugin_dirs=[],
        template_dir="templates",
        storage_dir="storage"
    )

@pytest.fixture
async def agent(config):
    """Create and initialize a workflow agent."""
    agent = WorkflowAgent(config)
    await agent.initialize()
    yield agent
    await agent.close()

@pytest.fixture
def script_path():
    """Create a test script path."""
    script_dir = Path("generated_scripts")
    script_dir.mkdir(exist_ok=True)
    
    script_path = script_dir / "test_script.ps1"
    script_path.write_text('Write-Host "Test script"')
    
    yield str(script_path)
    
    # Cleanup
    if script_path.exists():
        script_path.unlink()

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    yield str(test_dir)
    
    # Cleanup
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir) 