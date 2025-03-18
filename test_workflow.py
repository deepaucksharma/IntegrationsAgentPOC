#!/usr/bin/env python3
"""Test script for workflow agent."""
import asyncio
import yaml
import logging
import sys

from src.workflow_agent.agent import WorkflowAgent
from src.workflow_agent.utils.logging import setup_logging

async def test_install_monitoring_agent():
    """Test installing a monitoring agent."""
    # Load configuration
    with open('workflow_config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Modify config for testing
    config['configurable']['db_connection_string'] = 'workflow_history.db'
    config['configurable']['use_isolation'] = True  # Enable Docker isolation
    config['configurable']['isolation_method'] = 'docker'  # Explicitly set Docker as isolation method

    # State for installing monitoring agent
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
    
    # If successful, print the script that was generated
    if "script" in result and not result.get("error"):
        print("\nGenerated Script:")
        print(result["script"])
        
        # Save the script to a file
        with open('generated_script.sh', 'w') as f:
            f.write(result["script"])
        print("\nScript saved to 'generated_script.sh'")

    await agent.cleanup()

if __name__ == "__main__":
    setup_logging("DEBUG")
    asyncio.run(test_install_monitoring_agent())