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
from workflow_agent.verification.verifier import Verifier
from workflow_agent.verification.dynamic import DynamicVerificationBuilder

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("verification_tests.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_verification_state(
    target_name: str,
    integration_type: str,
    system_info: Dict[str, Any],
    verification_data: Dict[str, Any]
) -> WorkflowState:
    """Create a workflow state for verification."""
    return WorkflowState(
        action="verify",
        target_name=target_name,
        integration_type=integration_type,
        parameters={},
        system_context=system_info,
        template_data={"verification": verification_data}
    )

async def test_verification_script_generation(verifier: DynamicVerificationBuilder, state: WorkflowState) -> None:
    """Test verification script generation."""
    try:
        logger.info(f"Testing verification script generation for {state.target_name}")
        script = await verifier.build_verification_script(state)
        
        if script:
            # Save verification script
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_dir = Path("generated_scripts/verification")
            script_dir.mkdir(exist_ok=True, parents=True)
            
            ext = ".ps1" if "windows" in state.system_context["platform"]["system"].lower() else ".sh"
            filename = f"{state.target_name}_verify_{timestamp}{ext}"
            script_path = script_dir / filename
            
            with open(script_path, "w") as f:
                f.write(script)
            
            logger.info(f"Generated verification script saved to: {script_path}")
            return script_path
    except Exception as e:
        logger.error(f"Error generating verification script: {e}", exc_info=True)
        return None

async def test_verification_execution(agent: WorkflowAgent, state: WorkflowState, script_path: str) -> None:
    """Test verification script execution."""
    try:
        logger.info(f"Testing verification execution for {state.target_name}")
        
        # Update state with script
        with open(script_path, "r") as f:
            script = f.read()
        state = state.evolve(script=script)
        
        # Run verification
        result = await agent.run_workflow(state)
        logger.info(f"Verification execution completed with result: {result}")
        
        if result.error:
            logger.error(f"Verification failed: {result.error}")
        else:
            logger.info("Verification completed successfully")
            
    except Exception as e:
        logger.error(f"Error in verification execution: {e}", exc_info=True)

async def main():
    """Run verification workflow tests."""
    try:
        logger.info("Starting verification workflow tests...")
        
        # Initialize components
        message_bus = MessageBus()
        verifier = DynamicVerificationBuilder()
        
        # Load configuration
        config_path = "workflow_config.yaml"
        if not os.path.exists(config_path):
            raise ValueError(f"Configuration file not found at {config_path}")
        config = load_config_file(config_path)
        
        # Initialize WorkflowAgent
        agent = WorkflowAgent(config=config.get("configurable"))
        await agent.initialize()
        
        # Test Cases
        test_cases = [
            # Test Case 1: Windows Service Verification
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
                "verification_data": {
                    "steps": [
                        {
                            "name": "Check service status",
                            "command": "Get-Service 'newrelic-infra' | Select-Object Status"
                        },
                        {
                            "name": "Check port",
                            "command": "Test-NetConnection -ComputerName localhost -Port 8080"
                        },
                        {
                            "name": "Check config file",
                            "command": "Test-Path 'C:\\Program Files\\New Relic\\newrelic-infra\\newrelic-infra.yml'"
                        }
                    ]
                }
            },
            # Test Case 2: Linux Service Verification
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
                "verification_data": {
                    "steps": [
                        {
                            "name": "Check service status",
                            "command": "systemctl status newrelic-infra"
                        },
                        {
                            "name": "Check port",
                            "command": "netstat -tuln | grep 8080"
                        },
                        {
                            "name": "Check config file",
                            "command": "test -f /etc/newrelic-infra/newrelic-infra.yml"
                        }
                    ]
                }
            },
            # Test Case 3: Custom Integration Verification
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
                "verification_data": {
                    "steps": [
                        {
                            "name": "Check process",
                            "command": "pgrep -f custom-integration"
                        },
                        {
                            "name": "Check config file",
                            "command": "test -f /etc/newrelic-infra/integrations.d/custom-integration-config.yml"
                        },
                        {
                            "name": "Check logs",
                            "command": "test -f /var/log/newrelic/custom-integration.log"
                        }
                    ]
                }
            }
        ]
        
        # Run test cases
        for test_case in test_cases:
            state = create_verification_state(
                target_name=test_case["target_name"],
                integration_type=test_case["integration_type"],
                system_info=test_case["system_info"],
                verification_data=test_case["verification_data"]
            )
            
            # Generate and test verification script
            script_path = await test_verification_script_generation(verifier, state)
            if script_path:
                await test_verification_execution(agent, state, script_path)
        
        # Close agent
        await agent.close()
        logger.info("All verification tests completed")
        
    except Exception as e:
        logger.error(f"Error in test execution: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 