import pytest
from workflow_agent import WorkflowAgent, WorkflowAgentConfig
from workflow_agent.core.state import WorkflowState
from workflow_agent.error.exceptions import WorkflowError, ValidationError
import asyncio

@pytest.mark.asyncio
async def test_workflow_agent_initialization(workflow_agent: WorkflowAgent):
    """Test workflow agent initialization."""
    assert workflow_agent is not None
    assert workflow_agent.workflow_config is not None
    assert workflow_agent.history_manager is not None
    assert workflow_agent.script_generator is not None
    assert workflow_agent.script_validator is not None
    assert workflow_agent.script_executor is not None
    assert workflow_agent.verifier is not None
    assert workflow_agent.recovery_manager is not None

@pytest.mark.asyncio
async def test_workflow_agent_invoke_success(
    workflow_agent: WorkflowAgent,
    sample_workflow_state: WorkflowState,
    test_config: dict
):
    """Test successful workflow invocation."""
    result = await workflow_agent.invoke(sample_workflow_state, test_config)
    assert result.success
    assert "script" in result.output
    assert "changes" in result.output
    assert not result.error

@pytest.mark.asyncio
async def test_workflow_agent_invoke_invalid_state(
    workflow_agent: WorkflowAgent,
    test_config: dict
):
    """Test workflow invocation with invalid state."""
    invalid_state = WorkflowState(
        action="invalid_action",
        target_name="invalid_target"
    )
    result = await workflow_agent.invoke(invalid_state, test_config)
    assert not result.success
    assert result.error is not None

@pytest.mark.asyncio
async def test_workflow_agent_cleanup(workflow_agent: WorkflowAgent):
    """Test workflow agent cleanup."""
    await workflow_agent.cleanup()
    # Verify cleanup was successful by checking if we can still use the agent
    assert workflow_agent is not None
    assert workflow_agent.history_manager is not None

@pytest.mark.asyncio
async def test_workflow_agent_parameter_validation(
    workflow_agent: WorkflowAgent,
    test_config: dict
):
    """Test parameter validation in workflow agent."""
    state = WorkflowState(
        action="install",
        target_name="nginx",
        parameters={
            "version": "invalid_version",  # Invalid version format
            "port": "invalid_port"  # Invalid port type
        },
        integration_type="infra_agent",
        integration_category="webserver"
    )
    result = await workflow_agent.invoke(state, test_config)
    assert not result.success
    assert "validation" in result.error.lower()

@pytest.mark.asyncio
async def test_workflow_agent_retrieve_docs(
    workflow_agent: WorkflowAgent,
    test_config: dict
):
    """Test documentation retrieval functionality."""
    state = WorkflowState(
        action="retrieve_docs",
        target_name="nginx",
        integration_type="infra_agent",
        integration_category="webserver"
    )
    result = await workflow_agent.invoke(state, test_config)
    assert result.success
    assert "docs" in result.output
    assert "nginx" in result.output["docs"].lower()

@pytest.mark.asyncio
async def test_workflow_agent_dry_run(
    workflow_agent: WorkflowAgent,
    sample_workflow_state: WorkflowState,
    test_config: dict
):
    """Test dry run functionality."""
    state = WorkflowState(
        action="dry_run",
        target_name="nginx",
        parameters={
            "version": "1.18.0",
            "port": 80
        },
        integration_type="infra_agent",
        integration_category="webserver"
    )
    result = await workflow_agent.invoke(state, test_config)
    assert result.success
    assert "script" in result.output
    assert "changes" in result.output
    assert not result.error

@pytest.mark.asyncio
async def test_workflow_agent_error_handling(
    workflow_agent: WorkflowAgent,
    test_config: dict
):
    """Test error handling in workflow agent."""
    # Test with invalid configuration
    invalid_config = {"configurable": {"invalid_key": "invalid_value"}}
    state = WorkflowState(
        action="install",
        target_name="nginx",
        parameters={"version": "1.18.0"},
        integration_type="infra_agent",
        integration_category="webserver"
    )
    result = await workflow_agent.invoke(state, invalid_config)
    assert not result.success
    assert result.error is not None

@pytest.mark.asyncio
async def test_workflow_agent_concurrent_execution(
    workflow_agent: WorkflowAgent,
    test_config: dict
):
    """Test concurrent execution handling."""
    states = [
        WorkflowState(
            action="install",
            target_name=f"nginx_{i}",
            parameters={"version": "1.18.0"},
            integration_type="infra_agent",
            integration_category="webserver"
        )
        for i in range(3)
    ]
    
    results = await asyncio.gather(
        *[workflow_agent.invoke(state, test_config) for state in states]
    )
    
    assert all(result.success for result in results)
    assert len(set(result.output["transaction_id"] for result in results)) == 3 