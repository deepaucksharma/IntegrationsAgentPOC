import sys
import os
import logging
from workflow_agent.main import app

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("test_workflow.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting test workflow execution...")
logger.debug("Python version: %s", sys.version)
logger.debug("Python executable: %s", sys.executable)
logger.debug("Current directory: %s", os.getcwd())
logger.info("Attempting to run workflow agent...")

try:
    logger.info("Starting workflow agent test with parameters: install, infra_agent")
    logger.debug("Test parameters: license_key=test123, host=localhost")
    
    result = app(["install", "infra_agent", "--license-key", "test123", "--host", "localhost"])
    logger.info("Workflow execution completed successfully")
    logger.debug("Workflow result: %s", result)
    
    print("Workflow agent ran successfully!")
except KeyboardInterrupt:
    logger.warning("Workflow interrupted by user")
    print("\nWorkflow interrupted by user")
except Exception as e:
    logger.error("Error running workflow agent: %s", e, exc_info=True)
    print(f"Error running workflow agent: {e}")
    sys.exit(1) 