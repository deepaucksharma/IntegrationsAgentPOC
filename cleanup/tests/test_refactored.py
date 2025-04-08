"""Test the refactored script generation system."""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any
import platform

from workflow_agent.core.state import WorkflowState
from workflow_agent.scripting.generator import ScriptGenerator
from workflow_agent.scripting.llm_generator import LLMScriptGenerator
from workflow_agent.scripting.enhanced_generator import EnhancedScriptGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def get_system_context() -> Dict[str, Any]:
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

async def test_template_generator():
    """Test template-based script generation."""
    logger.info("Testing template-based script generation...")
    
    # Create test state
    state = WorkflowState(
        action="install",
        target_name="monitoring-agent",
        integration_type="infra_agent",
        parameters={
            "license_key": "test123",
            "host": "localhost",
            "port": "8080",
            "install_dir": "C:\\Program Files\\Test Agent" if platform.system().lower() == "windows" else "/opt/test-agent"
        },
        system_context=get_system_context()
    )
    
    # Create generator
    generator = ScriptGenerator(template_dir="./templates")
    
    # Generate script
    result = await generator.generate_script(state)
    
    # Check result
    if result.get("success", False):
        logger.info(f"Successfully generated script using template: {result.get('template_used')}")
        logger.info(f"Script saved to: {result.get('script_path')}")
        
        # Print snippet of script
        script = result.get("script", "")
        logger.info(f"Script snippet:\n{script[:200]}...")
    else:
        logger.error(f"Failed to generate script: {result.get('error')}")
    
    return result

async def test_llm_generator():
    """Test LLM-based script generation."""
    logger.info("Testing LLM-based script generation...")
    
    # Check for API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No GEMINI_API_KEY found in environment. Using a placeholder key for mock implementation.")
        api_key = "mock-api-key"
    
    # Create test state
    state = WorkflowState(
        action="install",
        target_name="monitoring-agent",
        integration_type="infra_agent",
        parameters={
            "license_key": "test123",
            "host": "localhost",
            "port": "8080",
            "install_dir": "C:\\Program Files\\Test Agent" if platform.system().lower() == "windows" else "/opt/test-agent"
        },
        system_context=get_system_context()
    )
    
    # Create generator with config
    config = {"gemini_api_key": api_key}
    generator = LLMScriptGenerator(config=config, template_dir="./templates")
    
    # Initialize the generator
    await generator.initialize()
    
    # Generate script
    result = await generator.generate_script(state)
    
    # Check result
    if result.get("success", False):
        logger.info(f"Successfully generated script using LLM")
        logger.info(f"Script saved to: {result.get('script_path')}")
        
        # Print snippet of script
        script = result.get("script", "")
        logger.info(f"Script snippet:\n{script[:200]}...")
    else:
        logger.error(f"Failed to generate script with LLM: {result.get('error')}")
    
    return result

async def test_enhanced_generator(template_script_path):
    """Test enhanced script generation."""
    logger.info("Testing enhanced script generation...")
    
    # Check for API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No GEMINI_API_KEY found in environment. Using a placeholder key for mock implementation.")
        api_key = "mock-api-key"
    
    # Create test state
    state = WorkflowState(
        action="install",
        target_name="monitoring-agent",
        integration_type="infra_agent",
        parameters={
            "license_key": "test123",
            "host": "localhost",
            "port": "8080",
            "install_dir": "C:\\Program Files\\Test Agent" if platform.system().lower() == "windows" else "/opt/test-agent"
        },
        system_context=get_system_context()
    )
    
    # Create generator with config
    config = {"gemini_api_key": api_key, "use_llm": True}
    generator = EnhancedScriptGenerator(config=config, template_dir="./templates")
    
    # Initialize the generator
    await generator.initialize()
    
    # Enhance script
    result = await generator.enhance_script(state, Path(template_script_path))
    
    # Check result
    if result.get("success", False):
        logger.info(f"Successfully enhanced script")
        logger.info(f"Enhanced script saved to: {result.get('script_path')}")
        
        # Print snippet of script
        script = result.get("script", "")
        logger.info(f"Enhanced script snippet:\n{script[:200]}...")
    else:
        logger.error(f"Failed to enhance script: {result.get('error')}")
    
    return result

async def main():
    """Run all tests."""
    try:
        # Test template-based generation
        template_result = await test_template_generator()
        
        # Test LLM-based generation
        llm_result = await test_llm_generator()
        
        # Test enhanced generation if template generation succeeded
        if template_result.get("success", False) and "script_path" in template_result:
            enhanced_result = await test_enhanced_generator(template_result["script_path"])
        else:
            logger.warning("Skipping enhanced test because template generation failed")
            enhanced_result = {"success": False, "error": "Template generation failed"}
            
        # Print summary
        logger.info("-" * 50)
        logger.info("Test Results Summary:")
        logger.info(f"Template Generation: {'SUCCESS' if template_result.get('success', False) else 'FAILED'}")
        logger.info(f"LLM Generation: {'SUCCESS' if llm_result.get('success', False) else 'FAILED'}")
        logger.info(f"Enhanced Generation: {'SUCCESS' if enhanced_result.get('success', False) else 'FAILED'}")
        logger.info("-" * 50)
        
    except Exception as e:
        logger.error(f"Test error: {e}", exc_info=True)
        
if __name__ == "__main__":
    asyncio.run(main())
