import asyncio
import logging
import os
import platform
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
        agent = WorkflowAgent(config=config.get("configurable"))
        await agent.initialize()
        logger.info("WorkflowAgent initialized successfully")

        # Define a sample workflow state
        logger.info("Creating workflow state...")
        state = WorkflowState(
            action="install",
            target_name="example-integration",
            integration_type="newrelic-infra-agent",
            parameters={"license_key": os.environ.get("NEW_RELIC_LICENSE_KEY", "YOUR_LICENSE_KEY")},
            system_context=get_system_context(),
            template_data={}
        )
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

        # Close the agent
        logger.info("Closing agent...")
        await agent.close()
        logger.info("Agent closed successfully")

    except Exception as e:
        logger.error(f"Error during workflow execution: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())