import asyncio
import logging
import os
from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    # Create a WorkflowAgent instance
    agent = WorkflowAgent()

    # Define a sample workflow state
    state = WorkflowState(
        action="install",
        target_name="example-integration",
        integration_type="newrelic-infra-agent",
        parameters={"license_key": os.environ.get("NEW_RELIC_LICENSE_KEY", "YOUR_LICENSE_KEY")}
    )

    # Run the workflow
    result = await agent.run_workflow(state)

    # Print the result
    print(result)

    # Close the agent
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())