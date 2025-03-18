"""Test script for workflow agent."""
import asyncio
import yaml
import logging
import sys

from src.workflow_agent.agent import WorkflowAgent
from src.workflow_agent.utils.logging import setup_logging

async def test_install_monitoring_agent():
    """Test installing a monitoring agent."""
    with open('workflow_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    # Modify config for testing
    config['configurable']['db_connection_string'] = 'workflow_history.db'
    config['configurable']['use_isolation'] = False  # speed up tests
    state = {
        "action": "install",
        "target_name": "monitoring_agent",
        "integration_type": "infra_agent",
        "parameters": {
            "license_key": "test_license"
        }
    }
    agent = WorkflowAgent()
    await agent.initialize(config)
    result = await agent.invoke(state, config)
    print("Result:", result)
    await agent.cleanup()

if __name__ == "__main__":
    setup_logging("DEBUG")
    asyncio.run(test_install_monitoring_agent())