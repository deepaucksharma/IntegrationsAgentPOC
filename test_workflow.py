"""Test workflow execution."""
import asyncio
import logging
import os
import platform
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState
from workflow_agent.config import load_config_file
from workflow_agent.multi_agent.improvement import ImprovementAgent
from workflow_agent.storage.knowledge_base import KnowledgeBase
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.scripting.generator import ScriptGenerator
from workflow_agent.utils.system import get_system_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_installation_workflow(agent: WorkflowAgent) -> Dict[str, Any]:
    """Test installation workflow."""
    logger.info("Testing installation workflow...")
    
    # Create workflow state
    state = WorkflowState(
        action="install",
        target_name="infrastructure-agent",
        integration_type="infra_agent",
        parameters={
            "license_key": "test123",
            "host": "localhost",
            "port": "8080",
            "log_level": "INFO",
            "install_dir": "C:\\Program Files\\Test Agent",
            "config_path": "C:\\ProgramData\\Test Agent\\config",
            "log_path": "C:\\ProgramData\\Test Agent\\logs"
        },
        system_context=get_system_context()
    )
    
    # Run workflow
    result = await agent.run_workflow(state)
    
    logger.info("Installation workflow completed: %s", result.model_dump())
    return result.model_dump()

async def test_verification_workflow(agent: WorkflowAgent) -> Dict[str, Any]:
    """Test verification workflow."""
    logger.info("Testing verification workflow...")
    
    # Create workflow state
    state = WorkflowState(
        action="verify",
        target_name="infrastructure-agent",
        integration_type="infra_agent",
        parameters={
            "host": "localhost",
            "port": "8080",
            "install_dir": "C:\\Program Files\\Test Agent",
            "config_path": "C:\\ProgramData\\Test Agent\\config",
            "log_path": "C:\\ProgramData\\Test Agent\\logs"
        },
        system_context=get_system_context()
    )
    
    # Run workflow
    result = await agent.run_workflow(state)
    
    logger.info("Verification workflow completed: %s", result.model_dump())
    return result.model_dump()

async def test_custom_integration_workflow(agent: WorkflowAgent) -> Dict[str, Any]:
    """Test custom integration workflow."""
    logger.info("Testing custom integration workflow...")
    
    # Create workflow state
    state = WorkflowState(
        action="install",
        target_name="custom-integration",
        integration_type="custom",
        parameters={
            "integration_url": "https://example.com/custom-integration",
            "config_path": "C:\\Program Files\\New Relic\\newrelic-infra\\integrations.d\\"
        },
        system_context=get_system_context()
    )
    
    # Run workflow
    result = await agent.run_workflow(state)
    
    logger.info("Custom integration workflow completed: %s", result.model_dump())
    return result.model_dump()

async def test_uninstallation_workflow(agent: WorkflowAgent) -> Dict[str, Any]:
    """Test uninstallation workflow."""
    logger.info("Testing uninstallation workflow...")
    
    # Create workflow state
    state = WorkflowState(
        action="uninstall",
        target_name="infrastructure-agent",
        integration_type="infra_agent",
        parameters={
            "install_dir": "C:\\Program Files\\Test Agent",
            "config_path": "C:\\ProgramData\\Test Agent\\config",
            "log_path": "C:\\ProgramData\\Test Agent\\logs"
        },
        system_context=get_system_context()
    )
    
    # Run workflow
    result = await agent.run_workflow(state)
    
    logger.info("Uninstallation workflow completed: %s", result.model_dump())
    return result.model_dump()

async def test_error_handling_workflow(agent: WorkflowAgent) -> Dict[str, Any]:
    """Test error handling and recovery."""
    logger.info("Testing error handling and recovery...")
    
    # Create workflow state with missing required parameter
    state = WorkflowState(
        action="install",
        target_name="infrastructure-agent",
        integration_type="infra_agent",
        parameters={
            "host": "localhost",
            "port": "8080"
        },
        system_context=get_system_context()
    )
    
    # Run workflow
    result = await agent.run_workflow(state)
    
    logger.info("Error handling workflow completed: %s", result.model_dump())
    
    # Check if error was handled as expected
    if not result.error:
        logger.warning("Expected error not found in result")
        
    return result.model_dump()

async def main():
    """Run all test workflows."""
    logger.info("Starting enhanced test workflow execution...")
    
    # Load configuration
    config = load_config_file("workflow_config.yaml")
    logger.info("Configuration loaded from workflow_config.yaml")
    
    # Initialize agent
    agent = WorkflowAgent(config)
    await agent.initialize()
    logger.info("WorkflowAgent initialized successfully")
    
    try:
        # Run test workflows
        results = {
            "INSTALL": await test_installation_workflow(agent),
            "VERIFY": await test_verification_workflow(agent),
            "CUSTOM": await test_custom_integration_workflow(agent),
            "UNINSTALL": await test_uninstallation_workflow(agent),
            "ERROR": await test_error_handling_workflow(agent)
        }
        
        # Print results summary
        print("\nTest Workflow Results Summary:")
        print("-" * 50)
        for test_name, result in results.items():
            error = result.get("error", "None")
            print(f"{test_name}: {'SUCCESS' if not error else 'FAILED'}")
            print(f"  Error: {error}")
        print("-" * 50)
        
        logger.info("All tests completed")
    finally:
        # Cleanup agent
        await agent.container.cleanup()

if __name__ == "__main__":
    asyncio.run(main())