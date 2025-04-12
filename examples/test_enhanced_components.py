"""
Test script to demonstrate the enhanced components.

This script showcases:
1. Enhanced workflow tracking through the WorkflowTracker
2. Template system with inheritance and conditional rendering
3. Knowledge base with caching and efficient retrieval
"""
import os
import sys
import logging
import asyncio
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import enhanced components
from src.workflow_agent.multi_agent.workflow_tracker import WorkflowTracker
from src.workflow_agent.multi_agent.recovery import WorkflowRecovery, RecoveryStrategy
from src.workflow_agent.templates.manager import TemplateManager
from src.workflow_agent.templates.validator import TemplateValidator
from src.workflow_agent.templates.conditional import ConditionalTemplateRenderer
from src.workflow_agent.storage.knowledge_base import KnowledgeBase
from src.workflow_agent.core.state import WorkflowState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_enhanced.log')
    ]
)
logger = logging.getLogger(__name__)

async def test_template_system():
    """Test the enhanced template system."""
    logger.info("Testing template system...")
    
    # Initialize template manager
    template_dirs = [
        os.path.join(Path(__file__).parent.parent, "templates"),
    ]
    manager = TemplateManager(template_dirs=template_dirs)
    
    # Create validator
    validator = TemplateValidator(manager)
    
    # Create conditional renderer
    renderer = ConditionalTemplateRenderer(manager)
    
    # Test finding templates
    system_context = {"is_windows": os.name == 'nt'}
    templates = await manager.find_templates_for_integration("infra_agent", "install", system_context)
    
    logger.info(f"Found {len(templates)} templates for infra_agent/install")
    for template in templates:
        logger.info(f"  - {template['path']} (score: {template.get('score', 0)})")
    
    # Create sample context
    context = {
        "parameters": {
            "license_key": "test-license-key",
            "host": "localhost",
            "port": "8080"
        },
        "action": "install",
        "integration_type": "infra_agent",
        "target_name": "infrastructure-agent",
        "system_context": system_context
    }
    
    # Test conditional rendering
    if templates:
        result = await renderer.render_template("install", "infra_agent", context)
        
        if result["success"]:
            logger.info(f"Successfully rendered template: {result['template_path']}")
            logger.info(f"First 100 characters of rendered template: {result['rendered'][:100]}...")
        else:
            logger.error(f"Error rendering template: {result.get('error', 'Unknown error')}")
    else:
        logger.warning("No templates found to render")

async def test_knowledge_base():
    """Test the enhanced knowledge base."""
    logger.info("Testing knowledge base...")
    
    # Initialize knowledge base
    kb = KnowledgeBase(storage_dir="knowledge")
    await kb.initialize()
    
    # Test creating and retrieving knowledge
    integration_type = "infra_agent"
    target_name = "infrastructure-agent"
    
    # Check if knowledge already exists
    docs = await kb.retrieve_documents(integration_type, target_name)
    
    if not docs:
        # Create sample knowledge
        definition = {
            "name": "New Relic Infrastructure Agent",
            "description": "Agent for monitoring system metrics",
            "version": "1.0.0",
            "parameters": [
                {
                    "name": "license_key",
                    "description": "New Relic license key",
                    "required": True,
                    "type": "string"
                },
                {
                    "name": "host",
                    "description": "Host to monitor",
                    "required": True,
                    "type": "string",
                    "default": "localhost"
                },
                {
                    "name": "port",
                    "description": "Port to use",
                    "required": False,
                    "type": "integer",
                    "default": 8080
                }
            ]
        }
        
        # Add document
        success = await kb.add_document(
            integration_type=integration_type,
            target_name=target_name,
            doc_type="definition",
            content=definition,
            source="test_script"
        )
        
        logger.info(f"Added knowledge base document: {success}")
    
    # Retrieve documents
    docs = await kb.retrieve_documents(integration_type, target_name)
    logger.info(f"Retrieved {len(docs)} documents for {integration_type}/{target_name}")
    
    # Test search
    search_results = await kb.search_knowledge(
        query="license key parameters",
        context={"integration_type": integration_type}
    )
    
    logger.info(f"Search returned {len(search_results)} results")
    for result in search_results:
        logger.info(f"  - {result['id']} (relevance: {result['relevance']})")

async def test_workflow_tracker():
    """Test the workflow tracker component."""
    logger.info("Testing workflow tracker...")
    
    # Initialize workflow tracker
    tracker = WorkflowTracker()
    
    # Create sample workflow
    workflow_id = "test-workflow"
    initial_state = {
        "action": "install",
        "integration_type": "infra_agent",
        "target_name": "infrastructure-agent",
        "parameters": {
            "license_key": "test-license-key",
            "host": "localhost"
        }
    }
    
    await tracker.create_workflow(workflow_id, initial_state)
    logger.info(f"Created workflow: {workflow_id}")
    
    # Create checkpoint
    await tracker.create_checkpoint(workflow_id, "initial")
    
    # Update workflow state
    updated_state = initial_state.copy()
    updated_state["status"] = "in_progress"
    updated_state["current_step"] = "knowledge_retrieval"
    
    await tracker.update_workflow(workflow_id, updated_state, "retrieve_knowledge")
    logger.info(f"Updated workflow: {workflow_id}")
    
    # Create another checkpoint
    await tracker.create_checkpoint(workflow_id, "knowledge_retrieved")
    
    # Get workflow history
    history = await tracker.get_workflow_history(workflow_id)
    logger.info(f"Workflow history has {len(history)} entries")
    
    # Test restoring checkpoint
    restored_state = await tracker.restore_checkpoint(workflow_id, "initial")
    logger.info(f"Restored workflow to initial checkpoint")
    
    # Clean up
    success = await tracker.delete_workflow(workflow_id)
    logger.info(f"Deleted workflow: {success}")

async def main():
    """Run all tests."""
    logger.info("Starting enhanced components test")
    
    try:
        # Test template system
        await test_template_system()
        
        # Test knowledge base
        await test_knowledge_base()
        
        # Test workflow tracker
        await test_workflow_tracker()
        
        logger.info("All tests completed successfully")
        
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
