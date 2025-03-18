import sys
import os
import logging
from workflow_agent.main import app

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Current directory: {os.getcwd()}")
print("\nTrying to run workflow agent...")

try:
    logger.info("Starting workflow agent test...")
    result = app(["install", "infra_agent", "--license-key", "test123", "--host", "localhost"])
    logger.info(f"Workflow result: {result}")
    print("Workflow agent ran successfully!")
except KeyboardInterrupt:
    print("\nWorkflow interrupted by user")
except Exception as e:
    logger.error(f"Error running workflow agent: {e}", exc_info=True)
    sys.exit(1) 