import asyncio
import logging
import os
import json
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState
from workflow_agent.config import load_config_file
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.verification.verifier import Verifier
from workflow_agent.verification.dynamic import DynamicVerificationBuilder
from workflow_agent.utils.system import get_system_context

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

def get_verification_test_cases() -> List[Dict[str, Any]]:
    """Get test cases for verification testing."""
    # Determine platform-specific details
    is_windows = "win" in platform.system().lower()
    system = "windows" if is_windows else "linux"
    distribution = "windows" if is_windows else "ubuntu"
    
    # Common file paths for different platforms
    if is_windows:
        paths = {
            "agent_config": "C:\\Program Files\\New Relic\\newrelic-infra\\newrelic-infra.yml",
            "custom_config": "C:\\Program Files\\New Relic\\newrelic-infra\\integrations.d\\custom-integration-config.yml",
            "log_file": "C:\\ProgramData\\New Relic\\logs\\newrelic-infra.log"
        }
    else:
        paths = {
            "agent_config": "/etc/newrelic-infra/newrelic-infra.yml",
            "custom_config": "/etc/newrelic-infra/integrations.d/custom-integration-config.yml",
            "log_file": "/var/log/newrelic/newrelic-infra.log"
        }
    
    return [
        # Infrastructure Agent - Basic
        {
            "name": "infra-agent-basic",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": distribution,
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "verification_data": {
                "steps": [
                    {
                        "name": "Check service status",
                        "command": "Get-Service 'newrelic-infra' | Select-Object Status" if is_windows 
                                 else "systemctl status newrelic-infra"
                    },
                    {
                        "name": "Check port",
                        "command": "Test-NetConnection -ComputerName localhost -Port 8080" if is_windows 
                                 else "netstat -tuln | grep 8080"
                    },
                    {
                        "name": "Check config file",
                        "command": f"Test-Path '{paths['agent_config']}'" if is_windows 
                                 else f"test -f {paths['agent_config']}"
                    }
                ]
            }
        },
        # Infrastructure Agent - Advanced
        {
            "name": "infra-agent-advanced",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": distribution,
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "verification_data": {
                "steps": [
                    {
                        "name": "Check service status",
                        "command": "Get-Service 'newrelic-infra' | Select-Object Status" if is_windows 
                                 else "systemctl status newrelic-infra"
                    },
                    {
                        "name": "Check process",
                        "command": "Get-Process -Name newrelic-infra -ErrorAction SilentlyContinue" if is_windows 
                                 else "pgrep -f newrelic-infra"
                    },
                    {
                        "name": "Check port",
                        "command": "Test-NetConnection -ComputerName localhost -Port 8080" if is_windows 
                                 else "netstat -tuln | grep 8080"
                    },
                    {
                        "name": "Check config file",
                        "command": f"Test-Path '{paths['agent_config']}'" if is_windows 
                                 else f"test -f {paths['agent_config']}"
                    },
                    {
                        "name": "Check log file",
                        "command": f"Test-Path '{paths['log_file']}'" if is_windows 
                                 else f"test -f {paths['log_file']}"
                    },
                    {
                        "name": "Check license key in config",
                        "command": f"Select-String -Path '{paths['agent_config']}' -Pattern 'license_key'" if is_windows 
                                 else f"grep 'license_key' {paths['agent_config']}"
                    }
                ]
            }
        },
        # Custom Integration
        {
            "name": "custom-integration",
            "target_name": "custom-integration",
            "integration_type": "custom",
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": distribution,
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "verification_data": {
                "steps": [
                    {
                        "name": "Check process",
                        "command": "Get-Process -Name custom-integration -ErrorAction SilentlyContinue" if is_windows 
                                 else "pgrep -f custom-integration"
                    },
                    {
                        "name": "Check config file",
                        "command": f"Test-Path '{paths['custom_config']}'" if is_windows 
                                 else f"test -f {paths['custom_config']}"
                    },
                    {
                        "name": "Check logs",
                        "command": f"Test-Path '{paths['log_file']}'" if is_windows 
                                 else f"test -f {paths['log_file']}"
                    }
                ]
            }
        },
        # Multiple Checks at Once
        {
            "name": "multi-verification",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": distribution,
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "verification_data": {
                "steps": [
                    {
                        "name": "Multiple checks - service and port",
                        "command": (
                            "$serviceRunning = (Get-Service 'newrelic-infra' -ErrorAction SilentlyContinue).Status -eq 'Running'; " +
                            "$portListening = (Test-NetConnection -ComputerName localhost -Port 8080 -WarningAction SilentlyContinue).TcpTestSucceeded; " +
                            "if($serviceRunning -and $portListening) { exit 0 } else { exit 1 }"
                        ) if is_windows else (
                            "systemctl is-active --quiet newrelic-infra && " +
                            "netstat -tuln | grep -q 8080"
                        )
                    }
                ]
            }
        },
        # Failed Verification
        {
            "name": "failed-verification",
            "target_name": "nonexistent-service",
            "integration_type": "infra_agent",
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": distribution,
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "verification_data": {
                "steps": [
                    {
                        "name": "Check nonexistent service",
                        "command": "Get-Service 'nonexistent-service' -ErrorAction Stop" if is_windows 
                                 else "systemctl status nonexistent-service"
                    }
                ]
            }
        }
    ]

async def test_verification_script_generation(verifier: DynamicVerificationBuilder, state: WorkflowState) -> Optional[Path]:
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
        return None
    except Exception as e:
        logger.error(f"Error generating verification script: {e}", exc_info=True)
        return None

async def test_verification_execution(agent: WorkflowAgent, state: WorkflowState, script_path: Path) -> Dict[str, Any]:
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
        
        return {
            "state": state.target_name,
            "integration_type": state.integration_type,
            "success": not bool(result.error),
            "error": result.error,
            "script_path": str(script_path)
        }
    except Exception as e:
        logger.error(f"Error in verification execution: {e}", exc_info=True)
        return {
            "state": state.target_name,
            "integration_type": state.integration_type,
            "success": False,
            "error": str(e),
            "script_path": str(script_path) if script_path else None
        }

async def test_direct_verification(verifier: Verifier, state: WorkflowState) -> Dict[str, Any]:
    """Test direct verification without script generation."""
    try:
        logger.info(f"Testing direct verification for {state.target_name}")
        
        # Create fake output with success
        from workflow_agent.core.state import OutputData
        output = OutputData(
            stdout="Verification successful",
            stderr="",
            exit_code=0,
            duration=0.1
        )
        
        # Add output to state
        state = state.evolve(output=output)
        
        # Run verification
        result = await verifier.verify_result(state)
        logger.info(f"Direct verification completed with result: {result}")
        
        return {
            "state": state.target_name,
            "integration_type": state.integration_type,
            "success": "error" not in result,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error in direct verification: {e}", exc_info=True)
        return {
            "state": state.target_name,
            "integration_type": state.integration_type,
            "success": False,
            "error": str(e)
        }

async def run_verification_workflow(test_case: Dict[str, Any], agent: WorkflowAgent, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a complete verification workflow for a test case."""
    logger.info(f"Running verification workflow for {test_case['name']}")
    
    # Create components
    verifier_builder = DynamicVerificationBuilder()
    verifier = Verifier()
    
    # Create state
    state = create_verification_state(
        target_name=test_case["target_name"],
        integration_type=test_case["integration_type"],
        system_info=test_case["system_info"],
        verification_data=test_case["verification_data"]
    )
    
    results = {
        "name": test_case["name"],
        "target_name": test_case["target_name"],
        "integration_type": test_case["integration_type"],
        "platform": test_case["system_info"]["platform"]["system"],
        "script_generation": False,
        "script_execution": False,
        "direct_verification": False
    }
    
    # Test script generation
    script_path = await test_verification_script_generation(verifier_builder, state)
    if script_path:
        results["script_generation"] = True
        results["script_path"] = str(script_path)
        
        # Test script execution
        execution_result = await test_verification_execution(agent, state, script_path)
        results["script_execution"] = execution_result["success"]
        if not execution_result["success"]:
            results["execution_error"] = execution_result.get("error")
    
    # Test direct verification
    direct_result = await test_direct_verification(verifier, state)
    results["direct_verification"] = direct_result["success"]
    if not direct_result["success"]:
        results["direct_error"] = direct_result.get("error")
    
    # Overall success
    results["success"] = results["script_generation"] and (
        results["script_execution"] or results["direct_verification"])
    
    return results

async def main():
    """Run verification workflow tests."""
    try:
        logger.info("Starting verification workflow tests...")
        
        # Load configuration
        config_path = "workflow_config.yaml"
        if not os.path.exists(config_path):
            logger.warning(f"Configuration file not found at {config_path}")
            config_path = None
        
        config = load_config_file(config_path) if config_path else None
        
        # Initialize WorkflowAgent
        agent = WorkflowAgent(config=config.get("configurable") if config else None)
        await agent.initialize()
        
        # Get test cases
        test_cases = get_verification_test_cases()
        
        # Run tests
        results = []
        for test_case in test_cases:
            logger.info(f"Testing verification for {test_case['name']}")
            result = await run_verification_workflow(test_case, agent, config)
            results.append(result)
        
        # Save results
        results_dir = Path("test_results")
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(results_dir / f"verification_results_{timestamp}.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print("\nVerification Test Results Summary:")
        print("-" * 50)
        for result in results:
            status = "SUCCESS" if result["success"] else "FAILED"
            print(f"{result['name']}: {status}")
            if not result["success"]:
                if not result["script_generation"]:
                    print("  - Script generation failed")
                if not result["script_execution"]:
                    print(f"  - Script execution failed: {result.get('execution_error', 'Unknown error')}")
                if not result["direct_verification"]:
                    print(f"  - Direct verification failed: {result.get('direct_error', 'Unknown error')}")
        print("-" * 50)
        
        # Close agent
        await agent.close()
        logger.info("All verification tests completed")
        
    except Exception as e:
        logger.error(f"Error in test execution: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())