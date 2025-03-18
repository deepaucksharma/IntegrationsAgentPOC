#!/usr/bin/env python3
"""
Main entry point for workflow agent with multi-agent system and documentation-based intelligence.
"""
import os
import sys
import asyncio
import logging
import typer
from typing import Optional
from pathlib import Path

from workflow_agent.core.message_bus import MessageBus
from workflow_agent.multi_agent.coordinator import CoordinatorAgent
from workflow_agent.multi_agent.knowledge import KnowledgeAgent
from workflow_agent.multi_agent.script_builder import ScriptBuilderAgent
from workflow_agent.multi_agent.execution import ExecutionAgent
from workflow_agent.multi_agent.improvement import ImprovementAgent
from workflow_agent.utils.logging import setup_logging
from workflow_agent.config.loader import load_config_file, find_default_config
from workflow_agent.storage.knowledge_base import KnowledgeBase
from workflow_agent.storage.history import HistoryManager
from workflow_agent.verification.dynamic import DynamicVerificationBuilder
from workflow_agent.rollback.recovery import RecoveryManager
from workflow_agent.utils.system import get_system_context

app = typer.Typer()
logger = logging.getLogger("workflow-agent")

@app.command()
def install(
    integration: str, 
    license_key: str = typer.Option(..., help="License key for the integration"),
    host: str = typer.Option("localhost", help="Host address for the integration"),
    config_path: Optional[str] = typer.Option(None, help="Path to configuration file")
):
    """
    Install a New Relic integration.
    """
    asyncio.run(_install_flow(integration, license_key, host, config_path))

async def _install_flow(integration: str, license_key: str, host: str, config_path: Optional[str]):
    setup_logging(log_level=os.environ.get("LOG_LEVEL", "INFO"))
    
    # Load configuration
    if not config_path:
        config_path = find_default_config()
    
    if config_path:
        logger.info(f"Loading configuration from {config_path}")
        try:
            config = load_config_file(config_path)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    else:
        logger.info("No configuration file found, using defaults")
        config = {}
    
    # Set up the multi-agent system
    message_bus = MessageBus()
    knowledge_base = KnowledgeBase()
    history_manager = HistoryManager()
    
    coordinator = CoordinatorAgent(message_bus)
    knowledge_agent = KnowledgeAgent(message_bus, knowledge_base)
    script_builder = ScriptBuilderAgent(message_bus)
    execution_agent = ExecutionAgent(message_bus)
    improvement_agent = ImprovementAgent(message_bus, knowledge_base)
    
    # Initialize agents
    await coordinator.initialize()
    await knowledge_agent.initialize()
    await script_builder.initialize()
    await execution_agent.initialize()
    await improvement_agent.initialize()
    await history_manager.initialize()
    
    # Create initial state
    from workflow_agent.core.state import WorkflowState
    system_context = get_system_context()
    
    state = WorkflowState(
        action="install",
        target_name=integration,
        integration_type=integration,
        parameters={
            "license_key": license_key,
            "host": host
        },
        system_context=system_context
    )
    
    try:
        result = await coordinator.start_workflow(state, config)
        workflow_id = result.get("workflow_id")
        
        if workflow_id:
            logger.info(f"Started workflow with ID: {workflow_id}")
            final_result = await coordinator.wait_for_completion(
                workflow_id,
                timeout=config.get("execution_timeout", 300)  # Use timeout directly in seconds
            )
            
            if "error" in final_result:
                typer.echo(f"Installation failed: {final_result['error']}")
                sys.exit(1)
            else:
                typer.echo(f"Installation successful: {final_result.get('status', 'completed')}")
        else:
            if "error" in result:
                typer.echo(f"Failed to start workflow: {result['error']}")
            else:
                typer.echo("Failed to start workflow")
            sys.exit(1)
    finally:
        await execution_agent.cleanup()
        await history_manager.cleanup()

@app.command()
def remove(
    integration: str,
    config_path: Optional[str] = typer.Option(None, help="Path to configuration file")
):
    """
    Remove a New Relic integration.
    """
    asyncio.run(_remove_flow(integration, config_path))

async def _remove_flow(integration: str, config_path: Optional[str]):
    setup_logging(log_level=os.environ.get("LOG_LEVEL", "INFO"))
    
    if not config_path:
        config_path = find_default_config()
    
    if config_path:
        try:
            config = load_config_file(config_path)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    else:
        config = {}
    
    message_bus = MessageBus()
    knowledge_base = KnowledgeBase()
    history_manager = HistoryManager()
    
    coordinator = CoordinatorAgent(message_bus)
    knowledge_agent = KnowledgeAgent(message_bus, knowledge_base)
    script_builder = ScriptBuilderAgent(message_bus)
    execution_agent = ExecutionAgent(message_bus)
    improvement_agent = ImprovementAgent(message_bus, knowledge_base)
    
    await coordinator.initialize()
    await knowledge_agent.initialize()
    await script_builder.initialize()
    await execution_agent.initialize()
    await improvement_agent.initialize()
    await history_manager.initialize()
    
    state = {
        "action": "remove",
        "target_name": integration,
        "integration_type": integration,
        "parameters": {},
        "system_context": {
            "platform": {
                "system": sys.platform,
                "distribution": "", # TODO: Determine how to get this
                "version": "" # TODO: Determine how to get this
            }
        }
    }
    
    try:
        result = await coordinator.start_workflow(state, config)
        workflow_id = result.get("workflow_id")
        
        if workflow_id:
            logger.info(f"Started workflow with ID: {workflow_id}")
            final_result = await coordinator.wait_for_completion(
                workflow_id,
                timeout=config.get("execution_timeout", 300)/1000
            )
            
            if "error" in final_result:
                typer.echo(f"Removal failed: {final_result['error']}")
                sys.exit(1)
            else:
                typer.echo(f"Removal successful: {final_result.get('status', 'completed')}")
        else:
            if "error" in result:
                typer.echo(f"Failed to start workflow: {result['error']}")
            else:
                typer.echo("Failed to start workflow")
            sys.exit(1)
    finally:
        await execution_agent.cleanup()
        await history_manager.cleanup()

@app.command()
def verify(
    integration: str,
    config_path: Optional[str] = typer.Option(None, help="Path to configuration file")
):
    """
    Verify a New Relic integration.
    """
    asyncio.run(_verify_flow(integration, config_path))

async def _verify_flow(integration: str, config_path: Optional[str]):
    setup_logging(log_level=os.environ.get("LOG_LEVEL", "INFO"))
    
    if not config_path:
        config_path = find_default_config()
    
    if config_path:
        try:
            config = load_config_file(config_path)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    else:
        config = {}
    
    message_bus = MessageBus()
    knowledge_base = KnowledgeBase()
    history_manager = HistoryManager()
    
    coordinator = CoordinatorAgent(message_bus)
    knowledge_agent = KnowledgeAgent(message_bus, knowledge_base)
    script_builder = ScriptBuilderAgent(message_bus)
    execution_agent = ExecutionAgent(message_bus)
    improvement_agent = ImprovementAgent(message_bus, knowledge_base)
    
    await coordinator.initialize()
    await knowledge_agent.initialize()
    await script_builder.initialize()
    await execution_agent.initialize()
    await improvement_agent.initialize()
    await history_manager.initialize()
    
    state = {
        "action": "verify",
        "target_name": integration,
        "integration_type": integration,
        "parameters": {},
        "system_context": {
            "platform": {
                "system": sys.platform,
                "distribution": "", # TODO: Determine how to get this
                "version": "" # TODO: Determine how to get this
            }
        }
    }
    
    try:
        result = await coordinator.start_workflow(state, config)
        workflow_id = result.get("workflow_id")
        
        if workflow_id:
            logger.info(f"Started workflow with ID: {workflow_id}")
            final_result = await coordinator.wait_for_completion(
                workflow_id,
                timeout=config.get("execution_timeout", 300)/1000
            )
            
            if "error" in final_result:
                typer.echo(f"Verification failed: {final_result['error']}")
                sys.exit(1)
            else:
                typer.echo(f"Verification successful: {final_result.get('status', 'completed')}")
        else:
            if "error" in result:
                typer.echo(f"Failed to start workflow: {result['error']}")
            else:
                typer.echo("Failed to start workflow")
            sys.exit(1)
    finally:
        await execution_agent.cleanup()
        await history_manager.cleanup()

if __name__ == "__main__":
    app()