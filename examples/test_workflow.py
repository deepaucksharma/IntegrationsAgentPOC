#!/usr/bin/env python3
"""
Test script for workflow agent multi-agent system.
"""
import asyncio
import yaml
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.workflow_agent.core.message_bus import MessageBus
from src.workflow_agent.multi_agent.coordinator import CoordinatorAgent
from src.workflow_agent.multi_agent.knowledge import KnowledgeAgent
from src.workflow_agent.multi_agent.script_builder import ScriptBuilderAgent
from src.workflow_agent.multi_agent.execution import ExecutionAgent
from src.workflow_agent.multi_agent.improvement import ImprovementAgent
from src.workflow_agent.storage.knowledge_base import KnowledgeBase
from src.workflow_agent.storage.history import HistoryManager

async def test_install_agent():
    """Test installing an agent using the multi-agent system."""
    # Load config
    config_paths = [
        'workflow_config.yaml',
        Path(__file__).parent.parent / 'workflow_config.yaml'
    ]
    
    config = None
    for config_path in config_paths:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            break
    
    if not config:
        config = {
            "configurable": {
                "use_isolation": True,
                "isolation_method": "docker",
                "docker_image": "ubuntu:latest",
                "execution_timeout": 30000,
                "log_level": "DEBUG"
            }
        }
    
    # Override for testing
    config['configurable']['use_isolation'] = True  # Use Docker for isolation
    
    # Construct multi-agent system
    message_bus = MessageBus()
    knowledge_base = KnowledgeBase()
    history_manager = HistoryManager()
    
    coordinator = CoordinatorAgent(message_bus)
    knowledge_agent = KnowledgeAgent(message_bus, knowledge_base)
    script_builder = ScriptBuilderAgent(message_bus)
    execution_agent = ExecutionAgent(message_bus)
    improvement_agent = ImprovementAgent(message_bus, knowledge_base)
    
    # Initialize
    await coordinator.initialize()
    await knowledge_agent.initialize()
    await script_builder.initialize()
    await execution_agent.initialize()
    await improvement_agent.initialize()
    
    # Prepare install state
    state = {
        "action": "install",
        "target_name": "monitoring_agent",
        "integration_type": "infra_agent",
        "parameters": {
            "license_key": "test_license_key",
            "host": "test.host.local"
        }
    }
    
    try:
        result = await coordinator.start_workflow(state, config)
        workflow_id = result.get("workflow_id")
        
        if workflow_id:
            print(f"Started workflow with ID: {workflow_id}")
            print("Waiting for completion...")
            
            final_result = await coordinator.wait_for_completion(workflow_id, timeout=60)
            if "error" in final_result:
                print(f"Installation failed: {final_result['error']}")
            else:
                print("Installation successful!")
                # Show generated script if present
                if "script" in final_result:
                    print("\nGenerated Script:")
                    print(final_result["script"])
                    # Save script to file
                    with open('generated_script.sh', 'w') as f:
                        f.write(final_result["script"])
                    print("\nScript saved to 'generated_script.sh'")
        else:
            print(f"Failed to start workflow: {result}")
    finally:
        await execution_agent.cleanup()
        await history_manager.cleanup()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(test_install_agent())