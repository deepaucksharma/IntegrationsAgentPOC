"""
Pytest configuration and fixtures.
"""
import pytest
import asyncio
import os
from pathlib import Path
from workflow_agent.main import WorkflowAgent
from workflow_agent.integrations.manager import IntegrationManager
from workflow_agent.integrations.verification import DynamicVerificationBuilder, Verifier
from workflow_agent.knowledge.integration import KnowledgeBase, DynamicIntegrationKnowledge
from workflow_agent.scripting.generator import ScriptGenerator, LLMScriptGenerator, EnhancedScriptGenerator
from workflow_agent.core.state import WorkflowState
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.utils.system import get_system_context
from workflow_agent.documentation.parser import DocumentationParser
from workflow_agent.strategy.installation import InstallationStrategyAgent

@pytest.fixture
def knowledge_base():
    return KnowledgeBase()

@pytest.fixture
def knowledge_manager():
    return DynamicIntegrationKnowledge()

@pytest.fixture
def generator():
    return ScriptGenerator()

@pytest.fixture
def llm_generator():
    return LLMScriptGenerator()

@pytest.fixture
def enhanced_generator():
    return EnhancedScriptGenerator()

@pytest.fixture
def verifier():
    return Verifier()

@pytest.fixture
def dynamic_verifier():
    return DynamicVerificationBuilder()

@pytest.fixture
def agent():
    return WorkflowAgent()

@pytest.fixture
def state():
    return WorkflowState(
        action="install",
        target_name="test-integration",
        integration_type="test",
        parameters={
            "license_key": "test123",
            "host": "localhost",
            "port": "8080"
        },
        system_context=get_system_context(),
        template_data={}
    )

@pytest.fixture
def doc_parser():
    return DocumentationParser()

@pytest.fixture
def docs():
    return {
        "definition": "Sample definition",
        "details": {}
    }

@pytest.fixture(scope="function")
def script_path():
    """Create a test script and return its path."""
    script_dir = Path("generated_scripts")
    script_dir.mkdir(exist_ok=True)
    script_path = script_dir / "test_script.ps1"
    with open(script_path, "w") as f:
        f.write("Write-Host 'Test script'")
    return script_path

@pytest.fixture
def script(script_path):
    with open(script_path, "r") as f:
        return f.read()

@pytest.fixture
def strategy_agent():
    return InstallationStrategyAgent()

@pytest.fixture
def message_bus():
    """Create a message bus instance."""
    return MessageBus()
