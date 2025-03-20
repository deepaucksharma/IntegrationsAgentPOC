import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState
from workflow_agent.config import load_config_file
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.knowledge.integration import DynamicIntegrationKnowledge
from workflow_agent.storage.knowledge_base import KnowledgeBase

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("knowledge_tests.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_knowledge_state(
    target_name: str,
    integration_type: str,
    system_info: Dict[str, Any],
    parameters: Dict[str, Any]
) -> WorkflowState:
    """Create a workflow state for knowledge testing."""
    return WorkflowState(
        action="install",
        target_name=target_name,
        integration_type=integration_type,
        parameters=parameters,
        system_context=system_info,
        template_data={}
    )

async def test_knowledge_retrieval(knowledge_base: KnowledgeBase, state: WorkflowState) -> None:
    """Test knowledge retrieval."""
    try:
        logger.info(f"Testing knowledge retrieval for {state.target_name}")
        
        # Retrieve documents
        docs = await knowledge_base.retrieve_documents(
            integration_type=state.integration_type,
            target_name=state.target_name,
            action=state.action
        )
        
        if docs:
            logger.info(f"Retrieved documents for {state.target_name}:")
            for key, value in docs.items():
                logger.info(f"- {key}: {type(value)}")
            
            # Save retrieved knowledge
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            knowledge_dir = Path("generated_knowledge")
            knowledge_dir.mkdir(exist_ok=True)
            
            knowledge_path = knowledge_dir / f"{state.target_name}_knowledge_{timestamp}.json"
            with open(knowledge_path, "w") as f:
                json.dump(docs, f, indent=2)
            
            logger.info(f"Saved knowledge to: {knowledge_path}")
            return docs
        else:
            logger.warning(f"No documents found for {state.target_name}")
            return None
            
    except Exception as e:
        logger.error(f"Error retrieving knowledge: {e}", exc_info=True)
        return None

async def test_knowledge_enhancement(knowledge_manager: DynamicIntegrationKnowledge, state: WorkflowState, docs: Dict[str, Any]) -> None:
    """Test knowledge enhancement."""
    try:
        logger.info(f"Testing knowledge enhancement for {state.target_name}")
        
        # Update state with retrieved docs
        state.template_data.update(docs)
        
        # Enhance state with documentation data
        enhanced_state = await knowledge_manager.enhance_workflow_state(state)
        
        if enhanced_state:
            logger.info(f"Enhanced state for {state.target_name}:")
            logger.info(f"- Platform specific docs: {bool(enhanced_state.template_data.get('platform_specific'))}")
            logger.info(f"- Platform info: {enhanced_state.template_data.get('platform_info')}")
            
            # Save enhanced state
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            enhanced_dir = Path("generated_knowledge/enhanced")
            enhanced_dir.mkdir(exist_ok=True, parents=True)
            
            enhanced_path = enhanced_dir / f"{state.target_name}_enhanced_{timestamp}.json"
            with open(enhanced_path, "w") as f:
                json.dump(enhanced_state.template_data, f, indent=2)
            
            logger.info(f"Saved enhanced state to: {enhanced_path}")
            return enhanced_state
        else:
            logger.warning(f"Failed to enhance state for {state.target_name}")
            return None
            
    except Exception as e:
        logger.error(f"Error enhancing knowledge: {e}", exc_info=True)
        return None

async def main():
    """Run knowledge workflow tests."""
    try:
        logger.info("Starting knowledge workflow tests...")
        
        # Initialize components
        message_bus = MessageBus()
        knowledge_base = KnowledgeBase()
        knowledge_manager = DynamicIntegrationKnowledge()
        
        # Initialize knowledge base
        await knowledge_base.initialize()
        
        # Test Cases
        test_cases = [
            # Test Case 1: Windows Infrastructure Agent
            {
                "target_name": "infrastructure-agent",
                "integration_type": "infra_agent",
                "system_info": {
                    "platform": {
                        "system": "windows",
                        "distribution": "windows",
                        "version": "10.0"
                    }
                },
                "parameters": {
                    "license_key": "test123",
                    "host": "localhost",
                    "port": "8080"
                }
            },
            # Test Case 2: Linux Infrastructure Agent
            {
                "target_name": "infrastructure-agent",
                "integration_type": "infra_agent",
                "system_info": {
                    "platform": {
                        "system": "linux",
                        "distribution": "ubuntu",
                        "version": "20.04"
                    }
                },
                "parameters": {
                    "license_key": "test123",
                    "host": "localhost",
                    "port": "8080"
                }
            },
            # Test Case 3: Custom Integration
            {
                "target_name": "custom-integration",
                "integration_type": "custom",
                "system_info": {
                    "platform": {
                        "system": "linux",
                        "distribution": "ubuntu",
                        "version": "20.04"
                    }
                },
                "parameters": {
                    "integration_url": "https://example.com/custom-integration",
                    "config_path": "/etc/newrelic-infra/integrations.d/"
                }
            }
        ]
        
        # Run test cases
        for test_case in test_cases:
            state = create_knowledge_state(
                target_name=test_case["target_name"],
                integration_type=test_case["integration_type"],
                system_info=test_case["system_info"],
                parameters=test_case["parameters"]
            )
            
            # Test knowledge retrieval
            docs = await test_knowledge_retrieval(knowledge_base, state)
            if docs:
                # Test knowledge enhancement
                await test_knowledge_enhancement(knowledge_manager, state, docs)
        
        logger.info("All knowledge tests completed")
        
    except Exception as e:
        logger.error(f"Error in test execution: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 