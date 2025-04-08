"""Test LLM-based workflow generation."""
import asyncio
import json
import logging
import os
import platform
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pytest

from workflow_agent.main import WorkflowAgent
from workflow_agent.core.state import WorkflowState
from workflow_agent.config import load_config_file
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.scripting.generator import ScriptGenerator
from workflow_agent.scripting.llm_generator import LLMScriptGenerator
from workflow_agent.scripting.enhanced_generator import EnhancedScriptGenerator, create_script_generator
from workflow_agent.utils.system import get_system_context
from workflow_agent.config.configuration import WorkflowConfiguration
from workflow_agent.llm.template_engine import TemplateEngine
from workflow_agent.llm.enhancer import ScriptEnhancer
from workflow_agent.execution.runner import ScriptRunner

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

def get_llm_test_cases() -> List[Dict[str, Any]]:
    """Define test cases for LLM-based script generation."""
    # Get platform info
    is_windows = "win" in platform.system().lower()
    system = "windows" if is_windows else "linux"
    
    # Get template paths
    template_dir = Path("src/workflow_agent/integrations/common_templates")
    template_paths = {
        "install": str(template_dir / "install" / ("infra_agent.ps1.j2" if is_windows else "infra_agent.sh.j2")),
        "verify": str(template_dir / "verify" / "infra_agent.sh.j2"),
        "uninstall": str(template_dir / "remove" / "infra_agent.sh.j2"),
        "custom_install": str(template_dir / "install" / "custom_integration.sh.j2")
    }
    
    # Define base test cases
    return [
        # Standard installation (Windows or Linux)
        {
            "name": "standard-install",
            "action": "install",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "parameters": {
                "license_key": "test123",
                "host": "localhost",
                "port": "8080",
                "log_level": "INFO",
                "install_dir": "C:\\Program Files\\New Relic" if is_windows else "/opt/newrelic"
            },
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": "windows" if is_windows else "ubuntu",
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "template_data": {
                "template_path": template_paths["install"],
                "version": "1.0.0",
                "verification_steps": [
                    "Test-NetConnection -ComputerName localhost -Port 8080" if is_windows else "curl -s http://localhost:8080/health",
                    "Get-Service 'newrelic-infra' | Select-Object Status" if is_windows else "systemctl status newrelic-infra"
                ],
                "required_tools": ["curl"],
                "version_command": (
                    "Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like '*New Relic Infrastructure*' } | Select-Object -ExpandProperty Version"
                    if is_windows else "newrelic-infra --version"
                )
            }
        },
        
        # Custom integration
        {
            "name": "custom-integration",
            "action": "install",
            "target_name": "custom-integration",
            "integration_type": "custom",
            "parameters": {
                "integration_url": "https://example.com/custom-integration",
                "config_path": "C:\\Program Files\\New Relic\\newrelic-infra\\integrations.d\\" if is_windows 
                                else "/etc/newrelic-infra/integrations.d/"
            },
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": "windows" if is_windows else "ubuntu",
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "template_data": {
                "template_path": template_paths["custom_install"],
                "version": "1.0.0",
                "name": "custom-integration"
            }
        },
        
        # Uninstallation
        {
            "name": "uninstall",
            "action": "uninstall",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "parameters": {
                "install_dir": "C:\\Program Files\\New Relic" if is_windows else "/opt/newrelic"
            },
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": "windows" if is_windows else "ubuntu",
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "template_data": {
                "template_path": template_paths["uninstall"],
                "version": "1.0.0"
            }
        },
        
        # Minimal parameters
        {
            "name": "minimal-params",
            "action": "install",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "parameters": {
                "license_key": "test123"
            },
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": "windows" if is_windows else "ubuntu",
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "template_data": {
                "template_path": template_paths["install"],
                "version": "1.0.0"
            }
        },
        
        # Complex parameters
        {
            "name": "complex-params",
            "action": "install",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "parameters": {
                "license_key": "test123",
                "host": "localhost",
                "port": "8080",
                "log_level": "DEBUG",
                "install_dir": "C:\\Program Files\\New Relic" if is_windows else "/opt/newrelic",
                "config_dir": "C:\\ProgramData\\New Relic" if is_windows else "/etc/newrelic",
                "proxy_host": "proxy.example.com",
                "proxy_port": "3128",
                "proxy_user": "proxyuser",
                "proxy_pass": "proxypass",
                "custom_attributes": {
                    "environment": "test",
                    "team": "devops",
                    "region": "us-east-1"
                }
            },
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": "windows" if is_windows else "ubuntu",
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "template_data": {
                "template_path": template_paths["install"],
                "version": "1.0.0"
            }
        },
        
        # Platform-specific installation
        {
            "name": "platform-specific",
            "action": "install",
            "target_name": "infrastructure-agent",
            "integration_type": "infra_agent",
            "parameters": {
                "license_key": "test123",
                "host": "localhost",
                "port": "8080",
                "log_level": "INFO",
                "install_dir": "C:\\Program Files\\New Relic" if is_windows else "/opt/newrelic",
                "platform_specific": {
                    "windows": {
                        "service_name": "newrelic-infra",
                        "service_display_name": "New Relic Infrastructure Agent",
                        "service_description": "New Relic Infrastructure Agent for monitoring",
                        "registry_key": "HKLM\\SOFTWARE\\New Relic\\Infrastructure"
                    },
                    "linux": {
                        "systemd_unit": "newrelic-infra.service",
                        "systemd_user": "newrelic",
                        "systemd_group": "newrelic",
                        "config_file": "/etc/newrelic-infra.yml"
                    }
                }
            },
            "system_info": {
                "platform": {
                    "system": system,
                    "distribution": "windows" if is_windows else "ubuntu",
                    "version": "10.0" if is_windows else "20.04"
                }
            },
            "template_data": {
                "template_path": template_paths["install"],
                "version": "1.0.0"
            }
        }
    ]

def setup_openai_api_key() -> None:
    """Set up OpenAI API key for testing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("No OpenAI API key found in environment. Tests will fail.")
        api_key = "mock-api-key-for-testing"  # This will cause a 401 error
    os.environ["OPENAI_API_KEY"] = api_key
    logger.info("OpenAI API key configured for testing")

def create_test_state(
    test_case: Dict[str, Any]
) -> WorkflowState:
    """Create a test workflow state from test case."""
    return WorkflowState(
        action=test_case["action"],
        target_name=test_case["target_name"],
        integration_type=test_case["integration_type"],
        parameters=test_case["parameters"],
        system_context=test_case["system_info"],
        template_data=test_case["template_data"]
    )

@pytest.mark.asyncio
async def test_script_generation_with_template(
    template_engine: TemplateEngine,
    state: WorkflowState
) -> Tuple[WorkflowState, Path]:
    """Test script generation using templates."""
    try:
        logger.info(f"Testing template-based script generation for {state.target_name}")
        
        # Generate script
        start_time = datetime.now()
        gen_result = await template_engine.generate_script(state)
        duration = (datetime.now() - start_time).total_seconds()
        
        result = {
            "method": "template",
            "success": gen_result is not None and "error" not in gen_result,
            "duration_seconds": duration
        }
        
        if not result["success"]:
            result["error"] = gen_result.get("error") if gen_result else "No result returned"
            logger.error(f"Template generation failed: {result['error']}")
            return result
        
        script = gen_result.get("script")
        if script:
            # Save generated script
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_dir = Path("generated_scripts")
            script_dir.mkdir(exist_ok=True)
            
            ext = ".ps1" if "windows" in state.system_context["platform"]["system"].lower() else ".sh"
            filename = f"{state.target_name}_{state.action}_template_{timestamp}{ext}"
            script_path = script_dir / filename
            
            with open(script_path, "w") as f:
                f.write(script)
            
            logger.info(f"Template-generated script saved to: {script_path}")
            result["script_path"] = str(script_path)
            result["script_size"] = len(script)
            
        return result
    except Exception as e:
        logger.error(f"Error in template script generation: {e}", exc_info=True)
        return {
            "method": "template",
            "success": False,
            "error": str(e)
        }

@pytest.mark.asyncio
async def test_script_generation_with_llm(
    script_generator: ScriptGenerator,
    state: WorkflowState
) -> Tuple[WorkflowState, Path]:
    """Test script generation using LLM."""
    try:
        logger.info(f"Testing LLM-based script generation for {state.target_name}")
        
        # Generate script
        start_time = datetime.now()
        gen_result = await script_generator.generate_script(state)
        duration = (datetime.now() - start_time).total_seconds()
        
        result = {
            "method": "llm",
            "success": gen_result is not None and "error" not in gen_result,
            "duration_seconds": duration
        }
        
        if not result["success"]:
            result["error"] = gen_result.get("error") if gen_result else "No result returned"
            logger.error(f"LLM generation failed: {result['error']}")
            return result
        
        script = gen_result.get("script")
        if script:
            # Save generated script
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_dir = Path("generated_scripts")
            script_dir.mkdir(exist_ok=True)
            
            ext = ".ps1" if "windows" in state.system_context["platform"]["system"].lower() else ".sh"
            filename = f"{state.target_name}_{state.action}_llm_{timestamp}{ext}"
            script_path = script_dir / filename
            
            with open(script_path, "w") as f:
                f.write(script)
            
            logger.info(f"LLM-generated script saved to: {script_path}")
            result["script_path"] = str(script_path)
            result["script_size"] = len(script)
            
        return result
    except Exception as e:
        logger.error(f"Error in LLM script generation: {e}", exc_info=True)
        return {
            "method": "llm",
            "success": False,
            "error": str(e)
        }

@pytest.mark.asyncio
async def test_script_generation_with_enhanced(
    script_enhancer: ScriptEnhancer,
    state: WorkflowState,
    script_path: Path
) -> Tuple[WorkflowState, Path]:
    """Test script enhancement."""
    try:
        logger.info(f"Testing enhanced script generation for {state.target_name}")
        
        # Generate script
        start_time = datetime.now()
        gen_result = await script_enhancer.enhance_script(state, script_path)
        duration = (datetime.now() - start_time).total_seconds()
        
        result = {
            "method": "enhanced",
            "success": "error" not in gen_result,
            "duration_seconds": duration
        }
        
        if "error" in gen_result:
            result["error"] = gen_result["error"]
            logger.error(f"Enhanced generation failed: {gen_result['error']}")
            return result
        
        script = gen_result.get("script")
        if script:
            # Save generated script
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_dir = Path("generated_scripts")
            script_dir.mkdir(exist_ok=True)
            
            ext = ".ps1" if "windows" in state.system_context["platform"]["system"].lower() else ".sh"
            filename = f"{state.target_name}_{state.action}_enhanced_{timestamp}{ext}"
            script_path = script_dir / filename
            
            with open(script_path, "w") as f:
                f.write(script)
            
            logger.info(f"Enhanced-generated script saved to: {script_path}")
            result["script_path"] = str(script_path)
            result["script_size"] = len(script)
            
        return result
    except Exception as e:
        logger.error(f"Error in enhanced script generation: {e}", exc_info=True)
        return {
            "method": "enhanced",
            "success": False,
            "error": str(e)
        }

@pytest.mark.asyncio
async def test_script_execution(
    script_runner: ScriptRunner,
    state: WorkflowState,
    script_path: Path
) -> Dict[str, Any]:
    """Test script execution."""
    try:
        logger.info(f"Testing script execution for {state.target_name}")
        
        # Apply script to state
        state_with_script = state.evolve(script=script_path.read_text())
        
        # Run workflow
        start_time = datetime.now()
        result = await script_runner.run_script(state_with_script)
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            "success": not bool(result.error),
            "duration_seconds": duration,
            "error": result.error,
            "exit_code": result.output.exit_code if result.output else None,
            "stdout_size": len(result.output.stdout) if result.output else 0,
            "stderr_size": len(result.output.stderr) if result.output else 0
        }
    except Exception as e:
        logger.error(f"Error in script execution: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "duration_seconds": 0
        }

async def run_llm_workflow_test(
    test_case: Dict[str, Any],
    agent: WorkflowAgent,
    template_generator: ScriptGenerator,
    llm_generator: LLMScriptGenerator,
    enhanced_generator: EnhancedScriptGenerator
) -> Dict[str, Any]:
    """Run complete LLM workflow test for a single test case."""
    logger.info(f"Running LLM workflow test: {test_case['name']}")
    
    # Create state
    state = create_test_state(test_case)
    
    results = {
        "name": test_case["name"],
        "target_name": test_case["target_name"],
        "integration_type": test_case["integration_type"],
        "action": test_case["action"],
        "platform": test_case["system_info"]["platform"]["system"],
        "generation_methods": {},
        "script_execution": {}
    }
    
    # Test template-based generation
    template_result = await test_script_generation_with_template(template_generator, state)
    results["generation_methods"]["template"] = template_result
    
    # Test LLM-based generation
    llm_result = await test_script_generation_with_llm(llm_generator, state)
    results["generation_methods"]["llm"] = llm_result
    
    # Test enhanced generation
    enhanced_result = await test_script_generation_with_enhanced(enhanced_generator, state, Path(template_result["script_path"]))
    results["generation_methods"]["enhanced"] = enhanced_result
    
    # Test execution of successfully generated scripts
    for method_name, method_result in results["generation_methods"].items():
        if method_result.get("success") and "script_path" in method_result:
            # Execute script
            execution_result = await test_script_execution(agent, state, Path(method_result["script_path"]))
            results["script_execution"][method_name] = execution_result
    
    return results

async def main():
    """Run LLM workflow tests."""
    try:
        logger.info("Starting LLM workflow tests...")
        
        # Load configuration
        config_path = Path("workflow_config.yaml")
        if not config_path.exists():
            raise ValueError("workflow_config.yaml not found")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize components
        agent = WorkflowAgent(config=config)
        await agent.initialize()
        
        template_generator = ScriptGenerator()
        llm_generator = LLMScriptGenerator(config)
        await llm_generator.initialize()
        
        enhanced_generator = EnhancedScriptGenerator()
        await enhanced_generator.initialize()
        
        # Get test cases
        test_cases = get_llm_test_cases()
        
        # Run tests
        results = []
        for test_case in test_cases:
            logger.info(f"Testing LLM workflow for {test_case['name']}")
            result = await run_llm_workflow_test(
                test_case, 
                agent, 
                template_generator, 
                llm_generator,
                enhanced_generator
            )
            results.append(result)
        
        # Save results
        results_dir = Path("test_results")
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(results_dir / f"llm_workflow_results_{timestamp}.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print("\nLLM Workflow Test Results Summary:")
        print("-" * 50)
        for result in results:
            print(f"Test: {result['name']} ({result['action']} {result['target_name']})")
            for method, gen_result in result["generation_methods"].items():
                print(f"  - {method} generation: {'SUCCESS' if gen_result['success'] else 'FAILED'}")
                if not gen_result["success"]:
                    print(f"    Error: {gen_result.get('error', 'Unknown error')}")
            
            if result["script_execution"]:
                for method, exec_result in result["script_execution"].items():
                    print(f"  - {method} execution: {'SUCCESS' if exec_result['success'] else 'FAILED'}")
                    if not exec_result["success"]:
                        print(f"    Error: {exec_result.get('error', 'Unknown error')}")
            else:
                print("  - No script executed")
        print("-" * 50)
        
        logger.info("All LLM workflow tests completed")
    
    except Exception as e:
        logger.error(f"Error during LLM workflow tests: {str(e)}")
        raise
    finally:
        # Cleanup
        if 'agent' in locals():
            await agent.container.cleanup()

if __name__ == "__main__":
    asyncio.run(main())