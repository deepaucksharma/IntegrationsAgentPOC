import pytest
import os
import asyncio
from typing import Dict, Any, Optional
from workflow_agent import WorkflowAgent, WorkflowAgentConfig
from workflow_agent.core.state import WorkflowState
from workflow_agent.storage import HistoryManager
from workflow_agent.scripting.generator import ScriptGenerator
from workflow_agent.scripting.validator import ScriptValidator
from workflow_agent.execution import ScriptExecutor
from workflow_agent.verification import Verifier
from workflow_agent.rollback.recovery import RecoveryManager

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Provide test configuration."""
    return {
        "configurable": {
            "template_dir": "tests/fixtures/templates",
            "use_isolation": False,
            "execution_timeout": 30,
            "skip_verification": True,
            "use_llm_optimization": False,
            "rule_based_optimization": True,
            "use_static_analysis": True,
            "db_connection_string": "sqlite+aiosqlite:///test_workflow.db",
            "prune_history_days": 7,
            "max_concurrent_tasks": 3
        }
    }

@pytest.fixture
def history_manager() -> HistoryManager:
    """Create a test history manager."""
    return HistoryManager("sqlite+aiosqlite:///test_workflow.db")

@pytest.fixture
def script_generator(history_manager: HistoryManager) -> ScriptGenerator:
    """Create a test script generator."""
    return ScriptGenerator(history_manager)

@pytest.fixture
def script_validator() -> ScriptValidator:
    """Create a test script validator."""
    return ScriptValidator()

@pytest.fixture
def script_executor(history_manager: HistoryManager) -> ScriptExecutor:
    """Create a test script executor."""
    return ScriptExecutor(
        history_manager,
        timeout=30,
        max_concurrent=3
    )

@pytest.fixture
def verifier() -> Verifier:
    """Create a test verifier."""
    return Verifier()

@pytest.fixture
def recovery_manager(history_manager: HistoryManager) -> RecoveryManager:
    """Create a test recovery manager."""
    return RecoveryManager(history_manager)

@pytest.fixture
def workflow_agent(
    history_manager: HistoryManager,
    script_generator: ScriptGenerator,
    script_validator: ScriptValidator,
    script_executor: ScriptExecutor,
    verifier: Verifier,
    recovery_manager: RecoveryManager
) -> WorkflowAgent:
    """Create a test workflow agent with all dependencies."""
    config = WorkflowAgentConfig(
        history_manager=history_manager,
        script_generator=script_generator,
        script_validator=script_validator,
        script_executor=script_executor,
        verifier=verifier,
        recovery_manager=recovery_manager,
        max_concurrent_tasks=3,
        use_isolation=False,
        execution_timeout=30
    )
    return WorkflowAgent(config)

@pytest.fixture
def sample_workflow_state() -> WorkflowState:
    """Create a sample workflow state for testing."""
    return WorkflowState(
        action="install",
        target_name="nginx",
        parameters={
            "version": "1.18.0",
            "port": 80
        },
        integration_type="infra_agent",
        integration_category="webserver",
        transaction_id="test-transaction-123"
    )

@pytest.fixture(autouse=True)
async def setup_test_env():
    """Setup test environment before each test."""
    # Create test directories
    os.makedirs("tests/fixtures/templates", exist_ok=True)
    os.makedirs("tests/fixtures/templates/rollback", exist_ok=True)
    
    # Create a basic test template
    template_path = "tests/fixtures/templates/webserver/nginx-install.sh"
    os.makedirs(os.path.dirname(template_path), exist_ok=True)
    
    with open(template_path, "w") as f:
        f.write("""#!/bin/bash
echo "Installing nginx version {{ parameters.version }}"
apt-get update
apt-get install -y nginx={{ parameters.version }}
systemctl enable nginx
systemctl start nginx
""")
    
    yield
    
    # Cleanup after tests
    if os.path.exists("test_workflow.db"):
        os.remove("test_workflow.db") 