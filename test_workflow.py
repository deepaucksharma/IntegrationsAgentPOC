import asyncio
import logging
import os
import platform
import sys
import json
from datetime import datetime
from pathlib import Path
from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState
from workflow_agent.config import load_config_file
from workflow_agent.multi_agent.improvement import ImprovementAgent
from workflow_agent.storage.knowledge_base import KnowledgeBase
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.scripting.generator import ScriptGenerator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("test_workflow.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_system_context():
    """Get system context information."""
    system = platform.system().lower()
    if system == "windows":
        return {
            "platform": {
                "system": "windows",
                "distribution": "windows",
                "version": platform.version()
            },
            "error_handling": {
                "continue_on_error": False
            }
        }
    elif system == "linux":
        try:
            import distro
            return {
                "platform": {
                    "system": "linux",
                    "distribution": distro.id(),
                    "version": distro.version()
                },
                "error_handling": {
                    "continue_on_error": False
                }
            }
        except ImportError:
            return {
                "platform": {
                    "system": "linux",
                    "distribution": platform.linux_distribution()[0].lower() if hasattr(platform, 'linux_distribution') else "",
                    "version": platform.version()
                },
                "error_handling": {
                    "continue_on_error": False
                }
            }
    else:
        return {
            "platform": {
                "system": system,
                "distribution": "",
                "version": platform.version()
            },
            "error_handling": {
                "continue_on_error": False
            }
        }

def save_generated_script(script: str, state: WorkflowState) -> str:
    """Save the generated script to a file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = Path("generated_scripts")
    script_dir.mkdir(exist_ok=True)
    
    # Determine script extension based on platform
    ext = ".ps1" if "windows" in state.system_context.get("platform", {}).get("system", "").lower() else ".sh"
    filename = f"{state.target_name}_{state.action}_{timestamp}{ext}"
    script_path = script_dir / filename
    
    with open(script_path, "w") as f:
        f.write(script)
    
    logger.info(f"Saved generated script to: {script_path}")
    return str(script_path)

async def main():
    try:
        logger.info("Starting test workflow execution...")
        logger.debug("Python version: %s", platform.python_version())
        logger.debug("Python executable: %s", sys.executable)
        logger.debug("Current directory: %s", os.getcwd())

        # Initialize components
        message_bus = MessageBus()
        knowledge_base = KnowledgeBase()
        improvement_agent = ImprovementAgent(message_bus, knowledge_base)
        await improvement_agent.initialize()

        # Load configuration
        config_path = "workflow_config.yaml"
        if not os.path.exists(config_path):
            raise ValueError(f"Configuration file not found at {config_path}")
        config = load_config_file(config_path)
        logger.info(f"Configuration loaded from {config_path}")

        # Initialize WorkflowAgent
        logger.info("Initializing WorkflowAgent...")
        agent = WorkflowAgent(config=config.get("configurable"))
        await agent.initialize()
        logger.info("WorkflowAgent initialized successfully")

        # Create workflow state with infrastructure agent parameters
        logger.info("Creating workflow state...")
        state = WorkflowState(
            action="install",
            target_name="infrastructure-agent",
            integration_type="infra_agent",
            parameters={
                "license_key": "test123",
                "host": "localhost",
                "port": "8080",
                "log_level": "INFO"
            },
            system_context=get_system_context(),
            template_data={
                "required_tools": ["curl", "wget"],
                "version": "1.0.0",
                "version_command": "infra-agent --version",
                "verification": {
                    "steps": [
                        "curl -s http://localhost:8080/health",
                        "infra-agent status"
                    ]
                },
                "selected_method": {
                    "steps": [
                        "wget https://example.com/infra-agent/1.0.0/infra-agent",
                        "chmod +x infra-agent",
                        "./infra-agent install --license-key test123 --host localhost --port 8080 --log-level INFO"
                    ]
                },
                "template_path": "src/workflow_agent/integrations/common_templates/install/infra_agent.ps1.j2"
            }
        )
        logger.info(f"Created workflow state: {state}")

        # Generate script
        logger.info("Generating script...")
        script_generator = ScriptGenerator()
        gen_result = await script_generator.generate_script(state, config.get("configurable"))
        if "error" in gen_result:
            raise ValueError(f"Script generation failed: {gen_result['error']}")
        
        script = gen_result.get("script")
        if script:
            script_path = save_generated_script(script, state)
            logger.info(f"Generated script saved to: {script_path}")
            state = state.evolve(script=script)

        # Run workflow
        logger.info("Starting workflow execution...")
        result = await agent.run_workflow(state)
        logger.info(f"Workflow execution completed with result: {result}")

        # Analyze for potential improvements
        if result.error:
            await message_bus.publish("analyze_failure", {
                "workflow_id": str(result.state_id),
                "state": result.dict(),
                "error": result.error
            })
        else:
            await message_bus.publish("workflow_complete", {
                "workflow_id": str(result.state_id),
                "state": result.dict(),
                "status": "completed"
            })

        # Print result
        print("\nWorkflow Result:")
        print("-" * 50)
        print(result)
        print("-" * 50)

        # Close agent
        logger.info("Closing agent...")
        await agent.close()
        logger.info("Agent closed successfully")

    except Exception as e:
        logger.error(f"Error during workflow execution: {str(e)}", exc_info=True)
        print(f"Error running workflow agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 