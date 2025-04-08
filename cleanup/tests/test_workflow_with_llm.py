"""Test workflow with enhanced script generation."""
import asyncio
import logging
import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from workflow_agent.core.state import WorkflowState
from workflow_agent.scripting.generator import ScriptGenerator
from workflow_agent.scripting.llm_generator import LLMScriptGenerator
from workflow_agent.scripting.enhanced_generator import EnhancedScriptGenerator
from workflow_agent.utils.system import get_system_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_workflow.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def get_test_system_context() -> Dict[str, Any]:
    """Get system context for tests."""
    is_windows = platform.system().lower() == "windows"
    
    return {
        "platform": {
            "system": "windows" if is_windows else "linux",
            "distribution": "windows" if is_windows else "ubuntu",
            "version": "10.0" if is_windows else "22.04"
        },
        "docker_available": False,
        "package_managers": {
            "apt": not is_windows,
            "yum": False,
            "chocolatey": is_windows,
            "scoop": is_windows
        }
    }

async def generate_scripts(state: WorkflowState, api_key: Optional[str] = None):
    """Generate scripts using all available methods."""
    results = {}
    
    # Generate using templates
    logger.info(f"Generating scripts for {state.action} on {state.target_name}")
    
    # Template-based generation
    template_generator = ScriptGenerator(template_dir="./templates")
    template_result = await template_generator.generate_script(state)
    if template_result.get("success", False):
        results["template"] = template_result
        logger.info(f"Template-based generation successful: {template_result.get('script_path')}")
    else:
        logger.error(f"Template-based generation failed: {template_result.get('error')}")
    
    # LLM-based generation
    config = {"gemini_api_key": api_key, "use_llm": True}
    llm_generator = LLMScriptGenerator(config=config, template_dir="./templates")
    await llm_generator.initialize()
    
    llm_result = await llm_generator.generate_script(state)
    if llm_result.get("success", False):
        results["llm"] = llm_result
        logger.info(f"LLM-based generation successful: {llm_result.get('script_path')}")
    else:
        logger.error(f"LLM-based generation failed: {llm_result.get('error')}")
    
    # Enhanced generation (if template generation succeeded)
    if "template" in results:
        enhanced_generator = EnhancedScriptGenerator(config=config, template_dir="./templates")
        await enhanced_generator.initialize()
        
        enhanced_result = await enhanced_generator.enhance_script(
            state, 
            Path(results["template"]["script_path"])
        )
        
        if enhanced_result.get("success", False):
            results["enhanced"] = enhanced_result
            logger.info(f"Enhanced generation successful: {enhanced_result.get('script_path')}")
        else:
            logger.error(f"Enhanced generation failed: {enhanced_result.get('error')}")
    
    return results

async def main():
    """Run a workflow with enhanced script generation."""
    try:
        logger.info("Starting workflow with enhanced script generation")
        
        # Check for API key
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("No GEMINI_API_KEY found in environment. Using a placeholder key for mock implementation.")
            api_key = "mock-api-key"
        
        # Test cases
        test_cases = [
            # Install
            {
                "action": "install",
                "target_name": "monitoring-agent",
                "integration_type": "infra_agent",
                "parameters": {
                    "license_key": "test123",
                    "host": "localhost",
                    "port": "8080",
                    "install_dir": "C:\\Program Files\\Test Agent" if platform.system().lower() == "windows" else "/opt/test-agent"
                }
            },
            # Verify
            {
                "action": "verify",
                "target_name": "monitoring-agent",
                "integration_type": "infra_agent",
                "parameters": {
                    "host": "localhost",
                    "port": "8080",
                    "install_dir": "C:\\Program Files\\Test Agent" if platform.system().lower() == "windows" else "/opt/test-agent"
                }
            },
            # Uninstall
            {
                "action": "uninstall",
                "target_name": "monitoring-agent",
                "integration_type": "infra_agent",
                "parameters": {
                    "install_dir": "C:\\Program Files\\Test Agent" if platform.system().lower() == "windows" else "/opt/test-agent"
                }
            }
        ]
        
        results = {}
        for i, test_case in enumerate(test_cases):
            logger.info(f"Running test case {i+1}/{len(test_cases)}: {test_case['action']} {test_case['target_name']}")
            
            # Create state
            state = WorkflowState(
                action=test_case["action"],
                target_name=test_case["target_name"],
                integration_type=test_case["integration_type"],
                parameters=test_case["parameters"],
                system_context=get_test_system_context()
            )
            
            # Generate scripts
            case_results = await generate_scripts(state, api_key)
            results[f"{test_case['action']}_{test_case['target_name']}"] = case_results
        
        # Print summary
        logger.info("-" * 50)
        logger.info("Script Generation Results Summary:")
        for case_name, case_results in results.items():
            logger.info(f"\nCase: {case_name}")
            for method, result in case_results.items():
                success = result.get("success", False)
                script_path = result.get("script_path", "N/A")
                logger.info(f"  - {method.capitalize()}: {'SUCCESS' if success else 'FAILED'} ({script_path})")
        logger.info("-" * 50)
        
    except Exception as e:
        logger.error(f"Workflow error: {e}", exc_info=True)
        
if __name__ == "__main__":
    asyncio.run(main())
