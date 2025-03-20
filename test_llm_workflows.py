import asyncio
import logging
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState
from workflow_agent.config import load_config_file
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.scripting.generator import ScriptGenerator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("llm_workflow_tests.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_test_state(
    action: str,
    target_name: str,
    integration_type: str,
    parameters: Dict[str, Any],
    system_info: Dict[str, Any],
    template_data: Dict[str, Any]
) -> WorkflowState:
    """Create a test workflow state."""
    return WorkflowState(
        action=action,
        target_name=target_name,
        integration_type=integration_type,
        parameters=parameters,
        system_context=system_info,
        template_data=template_data
    )

async def test_script_generation(agent: WorkflowAgent, state: WorkflowState) -> None:
    """Test script generation workflow."""
    logger.info(f"Testing script generation for {state.target_name} on {state.system_context['platform']['system']}")
    
    try:
        # Generate script
        script_generator = ScriptGenerator()
        gen_result = await script_generator.generate_script(state, {})
        
        if "error" in gen_result:
            logger.error(f"Script generation failed: {gen_result['error']}")
            return
        
        script = gen_result.get("script")
        if script:
            # Save generated script
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_dir = Path("generated_scripts")
            script_dir.mkdir(exist_ok=True)
            
            ext = ".ps1" if "windows" in state.system_context["platform"]["system"].lower() else ".sh"
            filename = f"{state.target_name}_{state.action}_{timestamp}{ext}"
            script_path = script_dir / filename
            
            with open(script_path, "w") as f:
                f.write(script)
            
            logger.info(f"Generated script saved to: {script_path}")
            state = state.evolve(script=script)
            
            # Run workflow
            result = await agent.run_workflow(state)
            logger.info(f"Workflow execution completed with result: {result}")
            
            if result.error:
                logger.error(f"Workflow failed: {result.error}")
            else:
                logger.info("Workflow completed successfully")
    
    except Exception as e:
        logger.error(f"Error in test execution: {e}", exc_info=True)

async def main():
    """Run LLM workflow tests."""
    try:
        logger.info("Starting LLM workflow tests...")
        
        # Initialize components
        message_bus = MessageBus()
        
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
            # Test Case 1: Windows Infrastructure Agent Installation
            {
                "action": "install",
                "target_name": "infrastructure-agent",
                "integration_type": "infra_agent",
                "parameters": {
                    "license_key": "test123",
                    "host": "localhost",
                    "port": "8080"
                },
                "system_info": {
                    "platform": {
                        "system": "windows",
                        "distribution": "windows",
                        "version": "10.0"
                    }
                },
                "template_data": {
                    "version": "1.0.0",
                    "verification_steps": [
                        "Test-NetConnection -ComputerName localhost -Port 8080",
                        "Get-Service 'newrelic-infra' | Select-Object Status"
                    ],
                    "template_path": "src/workflow_agent/integrations/common_templates/install/infra_agent.ps1.j2",
                    "required_tools": ["curl"],
                    "version_command": "Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like '*New Relic Infrastructure Agent*' } | Select-Object -ExpandProperty Version"
                }
            },
            # Test Case 2: Linux Infrastructure Agent Installation
            {
                "action": "install",
                "target_name": "infrastructure-agent",
                "integration_type": "infra_agent",
                "parameters": {
                    "license_key": "test123",
                    "host": "localhost",
                    "port": "8080"
                },
                "system_info": {
                    "platform": {
                        "system": "linux",
                        "distribution": "ubuntu",
                        "version": "20.04"
                    }
                },
                "template_data": {
                    "version": "1.0.0",
                    "verification_steps": [
                        "curl -s http://localhost:8080/health",
                        "systemctl status newrelic-infra"
                    ],
                    "template_path": "src/workflow_agent/integrations/common_templates/install/infra_agent.sh.j2",
                    "required_tools": ["curl"],
                    "version_command": "newrelic-infra --version"
                }
            },
            # Test Case 3: Custom Integration Installation
            {
                "action": "install",
                "target_name": "custom-integration",
                "integration_type": "custom",
                "parameters": {
                    "integration_url": "https://example.com/custom-integration",
                    "config_path": "/etc/newrelic-infra/integrations.d/"
                },
                "system_info": {
                    "platform": {
                        "system": "linux",
                        "distribution": "ubuntu",
                        "version": "20.04"
                    }
                },
                "template_data": {
                    "version": "1.0.0",
                    "verification_steps": [
                        "test -f /etc/newrelic-infra/integrations.d/custom-integration-config.yml",
                        "pgrep -f custom-integration"
                    ],
                    "template_path": "src/workflow_agent/integrations/common_templates/install/custom_integration.sh.j2",
                    "required_tools": ["curl"],
                    "version_command": "custom-integration --version"
                }
            }
        ]
        
        # Run test cases
        for test_case in test_cases:
            state = create_test_state(
                action=test_case["action"],
                target_name=test_case["target_name"],
                integration_type=test_case["integration_type"],
                parameters=test_case["parameters"],
                system_info=test_case["system_info"],
                template_data=test_case["template_data"]
            )
            await test_script_generation(agent, state)
        
        # Close agent
        await agent.close()
        logger.info("All tests completed")
        
    except Exception as e:
        logger.error(f"Error in test execution: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 