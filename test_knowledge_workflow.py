import asyncio
import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pytest

from workflow_agent.core.state import WorkflowState
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.knowledge.integration import DynamicIntegrationKnowledge
from workflow_agent.storage.knowledge_base import KnowledgeBase
from workflow_agent.documentation.parser import DocumentationParser
from workflow_agent.strategy.installation import InstallationStrategyAgent
from workflow_agent.utils.system import get_system_context

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("knowledge_workflow_tests.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define test cases for different platforms and integration types
def get_test_cases() -> List[Dict[str, Any]]:
    """Define test cases for knowledge workflows."""
    return [
        # Windows Infrastructure Agent
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
                "port": "8080",
                "install_dir": "C:\\Program Files\\New Relic"
            }
        },
        # Linux Infrastructure Agent - Ubuntu
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
                "port": "8080",
                "install_dir": "/opt/newrelic"
            }
        },
        # Linux Infrastructure Agent - RHEL/CentOS
        {
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "system_info": {
                "platform": {
                    "system": "linux",
                    "distribution": "centos",
                    "version": "8"
                }
            },
            "parameters": {
                "license_key": "test123",
                "host": "localhost",
                "port": "8080",
                "install_dir": "/opt/newrelic"
            }
        },
        # Custom Integration - Linux
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
        },
        # Custom Integration - Windows
        {
            "target_name": "custom-integration",
            "integration_type": "custom",
            "system_info": {
                "platform": {
                    "system": "windows",
                    "distribution": "windows",
                    "version": "10.0"
                }
            },
            "parameters": {
                "integration_url": "https://example.com/custom-integration",
                "config_path": "C:\\Program Files\\New Relic\\newrelic-infra\\integrations.d\\"
            }
        },
        # Monitoring Agent - Linux
        {
            "target_name": "monitoring-agent",
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
                "host": "localhost"
            }
        }
    ]

async def create_knowledge_state(
    target_name: str,
    integration_type: str,
    system_info: Dict[str, Any],
    parameters: Dict[str, Any],
    action: str = "install"
) -> WorkflowState:
    """Create a workflow state for knowledge testing."""
    return WorkflowState(
        action=action,
        target_name=target_name,
        integration_type=integration_type,
        parameters=parameters,
        system_context=system_info,
        template_data={}
    )

@pytest.mark.asyncio
async def test_knowledge_retrieval(
    knowledge_base: KnowledgeBase, 
    doc_parser: DocumentationParser,
    state: WorkflowState
) -> Tuple[Dict[str, Any], Path]:
    """Test knowledge retrieval from multiple sources."""
    try:
        logger.info(f"Testing knowledge retrieval for {state.integration_type}/{state.target_name}")
        
        # 1. Try local knowledge base first
        local_docs = await knowledge_base.retrieve_documents(
            integration_type=state.integration_type,
            target_name=state.target_name,
            action=state.action
        )
        
        # 2. If local docs unavailable, try documentation parser
        if not local_docs or not local_docs.get("definition"):
            logger.info(f"Local docs not found, fetching remote documentation for {state.target_name}")
            try:
                remote_docs = await doc_parser.fetch_integration_docs(state.integration_type)
                # Merge both sources if available
                if remote_docs:
                    if not local_docs:
                        local_docs = {}
                    local_docs["remote_docs"] = remote_docs
            except Exception as e:
                logger.warning(f"Error fetching remote docs: {e}")
        
        # Save retrieved knowledge
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        knowledge_dir = Path("generated_knowledge")
        knowledge_dir.mkdir(exist_ok=True)
        
        knowledge_path = knowledge_dir / f"{state.target_name}_{state.integration_type}_{timestamp}.json"
        with open(knowledge_path, "w") as f:
            json.dump(local_docs, f, indent=2, default=str)
        
        logger.info(f"Saved knowledge to: {knowledge_path}")
        return local_docs, knowledge_path
            
    except Exception as e:
        logger.error(f"Error retrieving knowledge: {e}", exc_info=True)
        raise

@pytest.mark.asyncio
async def test_knowledge_enhancement(
    knowledge_manager: DynamicIntegrationKnowledge, 
    state: WorkflowState, 
    docs: Dict[str, Any]
) -> Tuple[WorkflowState, Path]:
    """Test knowledge enhancement with platform-specific filtering."""
    try:
        logger.info(f"Testing knowledge enhancement for {state.target_name}")
        
        # Update state with retrieved docs
        if state.template_data is None:
            state.template_data = {}
        state.template_data.update(docs)
        
        # Enhance state with documentation data
        enhanced_state = await knowledge_manager.enhance_workflow_state(state)
        
        # Save enhanced state
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        enhanced_dir = Path("generated_knowledge/enhanced")
        enhanced_dir.mkdir(exist_ok=True, parents=True)
        
        enhanced_path = enhanced_dir / f"{state.target_name}_{state.integration_type}_{timestamp}.json"
        with open(enhanced_path, "w") as f:
            json.dump(
                {
                    "action": enhanced_state.action,
                    "target_name": enhanced_state.target_name,
                    "integration_type": enhanced_state.integration_type,
                    "parameters": enhanced_state.parameters,
                    "template_data": enhanced_state.template_data
                },
                f, 
                indent=2,
                default=str
            )
        
        logger.info(f"Saved enhanced state to: {enhanced_path}")
        return enhanced_state, enhanced_path
            
    except Exception as e:
        logger.error(f"Error enhancing knowledge: {e}", exc_info=True)
        raise

@pytest.mark.asyncio
async def test_strategy_selection(
    strategy_agent: InstallationStrategyAgent,
    state: WorkflowState
) -> Tuple[WorkflowState, Path]:
    """Test installation strategy selection."""
    try:
        logger.info(f"Testing strategy selection for {state.target_name}")
        
        # Select strategy
        strategy_state = await strategy_agent.determine_best_approach(state)
        
        # Save strategy selection
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy_dir = Path("generated_knowledge/strategy")
        strategy_dir.mkdir(exist_ok=True, parents=True)
        
        strategy_path = strategy_dir / f"{state.target_name}_{state.integration_type}_{timestamp}.json"
        with open(strategy_path, "w") as f:
            strategy_data = {
                "action": strategy_state.action,
                "target_name": strategy_state.target_name,
                "integration_type": strategy_state.integration_type,
                "selected_method": strategy_state.template_data.get("selected_method"),
                "method_scores": strategy_state.template_data.get("method_scores")
            }
            json.dump(strategy_data, f, indent=2, default=str)
        
        logger.info(f"Saved strategy selection to: {strategy_path}")
        return strategy_state, strategy_path
            
    except Exception as e:
        logger.error(f"Error selecting strategy: {e}", exc_info=True)
        raise

async def run_knowledge_workflow(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run complete knowledge workflow for a test case."""
    try:
        # Initialize components
        message_bus = MessageBus()
        knowledge_base = KnowledgeBase()
        knowledge_manager = DynamicIntegrationKnowledge()
        doc_parser = DocumentationParser()
        strategy_agent = InstallationStrategyAgent()
        
        # Initialize knowledge base
        await knowledge_base.initialize()
        
        result = {
            "target_name": test_case["target_name"],
            "integration_type": test_case["integration_type"],
            "platform": test_case["system_info"]["platform"],
            "status": "failed"
        }
        
        # Create state
        state = await create_knowledge_state(
            target_name=test_case["target_name"],
            integration_type=test_case["integration_type"],
            system_info=test_case["system_info"],
            parameters=test_case["parameters"]
        )
        
        # Run knowledge retrieval
        docs, knowledge_path = await test_knowledge_retrieval(
            knowledge_base, 
            doc_parser, 
            state
        )
        result["knowledge_path"] = str(knowledge_path)
        
        if docs:
            # Run knowledge enhancement
            enhanced_state, enhanced_path = await test_knowledge_enhancement(
                knowledge_manager, 
                state, 
                docs
            )
            result["enhanced_path"] = str(enhanced_path)
            
            # Run strategy selection
            strategy_state, strategy_path = await test_strategy_selection(
                strategy_agent,
                enhanced_state
            )
            result["strategy_path"] = str(strategy_path)
            
            result["status"] = "success"
            
        return result
        
    except Exception as e:
        logger.error(f"Error in knowledge workflow: {e}", exc_info=True)
        return {
            "target_name": test_case["target_name"],
            "integration_type": test_case["integration_type"],
            "platform": test_case["system_info"]["platform"],
            "status": "failed",
            "error": str(e)
        }

async def main():
    """Run knowledge workflow tests for all test cases."""
    try:
        logger.info("Starting knowledge workflow tests...")
        
        # Get test cases
        test_cases = get_test_cases()
        
        # Run workflow for each test case
        results = []
        for i, test_case in enumerate(test_cases):
            logger.info(f"Running knowledge workflow test {i+1}/{len(test_cases)}: "
                      f"{test_case['integration_type']}/{test_case['target_name']} "
                      f"on {test_case['system_info']['platform']['system']}")
            
            result = await run_knowledge_workflow(test_case)
            results.append(result)
            
            logger.info(f"Test {i+1}/{len(test_cases)} completed with status: {result['status']}")
        
        # Save overall results
        results_dir = Path("test_results")
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(results_dir / f"knowledge_results_{timestamp}.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print("\nKnowledge Workflow Test Results Summary:")
        print("-" * 50)
        for i, result in enumerate(results):
            status = result["status"].upper()
            print(f"Test {i+1}: {result['integration_type']}/{result['target_name']} - {status}")
            if result["status"] == "failed" and "error" in result:
                print(f"  Error: {result['error']}")
        print("-" * 50)
        
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"All knowledge tests completed. Success: {success_count}/{len(results)}")
        
    except Exception as e:
        logger.error(f"Error in test execution: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())