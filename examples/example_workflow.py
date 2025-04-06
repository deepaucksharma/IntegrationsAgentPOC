import asyncio
import logging
import os
import platform
from datetime import datetime
from pathlib import Path
from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState
from workflow_agent.config import load_config_file, find_default_config

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
                }
            }
        except ImportError:
            return {
                "platform": {
                    "system": "linux",
                    "distribution": platform.linux_distribution()[0].lower() if hasattr(platform, 'linux_distribution') else "",
                    "version": platform.version()
                }
            }
    else:
        return {
            "platform": {
                "system": system,
                "distribution": "",
                "version": platform.version()
            }
        }

async def main():
    try:
        logger.info("Loading configuration...")
        # Get the path to the configuration file relative to the examples directory
        config_path = str(Path(__file__).parent.parent / "workflow_config.yaml")
        if not os.path.exists(config_path):
            raise ValueError(f"Configuration file not found at {config_path}")
        config = load_config_file(config_path)
        logger.info(f"Configuration loaded from {config_path}")

        logger.info("Initializing WorkflowAgent...")
        # Create a WorkflowAgent instance
        agent = WorkflowAgent(config=config.configurable if hasattr(config, "configurable") else config)
        # WorkflowAgent initializes its components in the constructor
        logger.info("WorkflowAgent initialized successfully")

        # Create parameters dictionary
        params = {
            "license_key": os.environ.get("NEW_RELIC_LICENSE_KEY", "YOUR_LICENSE_KEY"),
            "host": "localhost",
            "port": "8080",
            "install_dir": r"C:\Program Files\New Relic",
            "config_path": r"C:\ProgramData\New Relic",
            "log_path": r"C:\ProgramData\New Relic\logs"
        }
        
        # Get system context to check if we're on Windows
        sys_context = get_system_context()
        
        # Create context for template - all top-level keys
        template_context = {
            "action": "install",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parameters": params  # Include parameters as a nested dictionary
        }
        
        # Create the state object
        state = WorkflowState(
            action="install",
            target_name="infrastructure-agent",  # A supported target
            integration_type="infra_agent",      # Match the plugin name 
            parameters=params,
            system_context=sys_context,
            template_data=template_context
        )
        
        # Then set the template_key attribute directly based on platform
        if sys_context.get('platform', {}).get('system') == 'windows':
            state = state.evolve(template_key="install/infra_agent.ps1")
        
        logger.info(f"Created workflow state: {state}")

        # Run the workflow
        logger.info("Starting workflow execution...")
        result = await agent.run_workflow(state)
        logger.info(f"Workflow execution completed with result: {result}")

        # Print the result
        print("\nWorkflow Result:")
        print("-" * 50)
        print(result)
        print("-" * 50)

        # Close the agent (we're adding a check for the close method)
        logger.info("Closing agent...")
        if hasattr(agent, 'close') and callable(getattr(agent, 'close')):
            await agent.close()
            logger.info("Agent closed successfully")
        else:
            logger.info("No close method available on agent")

    except Exception as e:
        logger.error(f"Error during workflow execution: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())