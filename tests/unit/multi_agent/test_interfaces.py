"""
Unit tests for multi-agent interfaces implementation.
These tests validate that the refactored multi-agent components correctly implement their interfaces.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from workflow_agent.multi_agent.base import MultiAgentBase, MultiAgentMessage, MessageType
from workflow_agent.multi_agent.interfaces import (
    KnowledgeAgentInterface,
    ExecutionAgentInterface,
    VerificationAgentInterface,
    ImprovementAgentInterface
)
from workflow_agent.multi_agent.knowledge import KnowledgeAgent
from workflow_agent.multi_agent.execution import ExecutionAgent
from workflow_agent.multi_agent.improvement import ImprovementAgent

# Fixtures for testing
@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for testing."""
    coordinator = AsyncMock()
    coordinator.route_message = AsyncMock(return_value=True)
    return coordinator

@pytest.fixture
def mock_message_bus():
    """Create a mock message bus for testing."""
    message_bus = AsyncMock()
    message_bus.publish = AsyncMock()
    message_bus.subscribe = AsyncMock()
    message_bus.unsubscribe = AsyncMock()
    return message_bus

@pytest.fixture
def test_message():
    """Create a test message for interface testing."""
    return MultiAgentMessage(
        sender="test_sender",
        message_type=MessageType.KNOWLEDGE_REQUEST,
        content={"query": "test query"},
        metadata={"workflow_id": "test123"}
    )

# Tests for KnowledgeAgent
@pytest.mark.asyncio
async def test_knowledge_agent_interfaces(mock_coordinator, mock_message_bus):
    """Test that KnowledgeAgent implements KnowledgeAgentInterface correctly."""
    # Create the agent
    agent = KnowledgeAgent(mock_message_bus)
    
    # Verify it implements the interface
    assert isinstance(agent, KnowledgeAgentInterface), "KnowledgeAgent should implement KnowledgeAgentInterface"
    
    # Test required interface methods
    assert hasattr(agent, "retrieve_knowledge"), "KnowledgeAgent should have retrieve_knowledge method"
    assert hasattr(agent, "update_knowledge_base"), "KnowledgeAgent should have update_knowledge_base method"
    assert hasattr(agent, "validate_knowledge"), "KnowledgeAgent should have validate_knowledge method"
    
    # Basic functionality test
    with patch.object(agent, '_process_knowledge_query', AsyncMock(return_value={"answer": "test"})):
        result = await agent.retrieve_knowledge("test query")
        assert "query" in result, "retrieve_knowledge should return a dict with 'query' key"
        assert "source" in result, "retrieve_knowledge should return a dict with 'source' key"

# Tests for ExecutionAgent
@pytest.mark.asyncio
async def test_execution_agent_interfaces(mock_coordinator, mock_message_bus):
    """Test that ExecutionAgent implements ExecutionAgentInterface correctly."""
    # Create the agent
    agent = ExecutionAgent(mock_message_bus)
    
    # Verify it implements the interface
    assert isinstance(agent, ExecutionAgentInterface), "ExecutionAgent should implement ExecutionAgentInterface"
    
    # Test required interface methods
    assert hasattr(agent, "execute_task"), "ExecutionAgent should have execute_task method"
    assert hasattr(agent, "validate_execution"), "ExecutionAgent should have validate_execution method"
    assert hasattr(agent, "handle_execution_error"), "ExecutionAgent should have handle_execution_error method"
    
    # Basic functionality test
    with patch.object(agent.executor, 'run_script', AsyncMock(return_value={"success": True, "output": "test output"})):
        result = await agent.execute_task({"script": "echo test", "action": "test"})
        assert "success" in result, "execute_task should return a dict with 'success' key"

# Tests for ImprovementAgent
@pytest.mark.asyncio
async def test_improvement_agent_interfaces(mock_coordinator, mock_message_bus):
    """Test that ImprovementAgent implements ImprovementAgentInterface correctly."""
    # Create the agent
    agent = ImprovementAgent(mock_message_bus)
    
    # Verify it implements the interface
    assert isinstance(agent, ImprovementAgentInterface), "ImprovementAgent should implement ImprovementAgentInterface"
    
    # Test required interface methods
    assert hasattr(agent, "analyze_performance"), "ImprovementAgent should have analyze_performance method"
    assert hasattr(agent, "generate_improvements"), "ImprovementAgent should have generate_improvements method"
    assert hasattr(agent, "learn_from_execution"), "ImprovementAgent should have learn_from_execution method"
    
    # Basic functionality test
    result = await agent.analyze_performance({
        "integration_type": "test",
        "action": "install",
        "error_count": 1,
        "success_rate": 0.5
    })
    assert "improvement_areas" in result, "analyze_performance should return improvement areas"

# Tests for message handling
@pytest.mark.asyncio
async def test_message_handling(mock_coordinator, test_message):
    """Test that agents can properly handle messages through the interfaces."""
    # Create a test agent that implements MultiAgentBase
    class TestAgent(MultiAgentBase):
        async def _handle_message(self, message):
            self.last_message = message
            return True
            
    # Initialize agent with coordinator
    agent = TestAgent(mock_coordinator, "test_agent")
    
    # Test receiving message
    await agent.receive_message(test_message)
    
    # Check that it was processed
    await asyncio.sleep(0.1)  # Give time for async message processing
    assert hasattr(agent, "last_message"), "Agent should have processed the message"
    if hasattr(agent, "last_message"):
        assert agent.last_message.message_type == test_message.message_type, "Message type should match"
