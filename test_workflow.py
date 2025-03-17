import asyncio
import yaml
from workflow_agent.agent import WorkflowAgent, WorkflowAgentConfig
from workflow_agent.core.state import WorkflowState

async def test_install_monitoring_agent():
    """Test installing a monitoring agent."""
    # Load configuration
    with open('workflow_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Add SQLite path and disable isolation
    config['configurable']['db_connection_string'] = 'workflow_history.db'
    config['configurable']['use_isolation'] = False
    
    # Create workflow state
    state = {
        "action": "install",
        "target_name": "monitoring_agent",
        "integration_type": "infra_agent",
        "parameters": {
            "api_key": "test_api_key",
            "endpoint": "https://monitoring.example.com"
        }
    }
    
    # Create agent config
    agent_config = WorkflowAgentConfig(
        max_concurrent_tasks=5,
        use_isolation=False,
        isolation_method="direct",
        execution_timeout=30000,
        skip_verification=False,
        use_llm_optimization=False,
        rule_based_optimization=True,
        use_static_analysis=True
    )
    
    # Create and initialize agent
    agent = WorkflowAgent(config=agent_config)
    await agent.initialize(config)
    
    try:
        # Execute workflow
        result = await agent.invoke(state, config)
        print("\nInstallation Result:")
        print(f"Success: {'error' not in result}")
        if 'error' in result:
            print(f"Error: {result['error']}")
        if 'output' in result:
            print(f"Output: {result['output']}")
    finally:
        await agent.cleanup()

async def test_remove_monitoring_agent():
    """Test removing a monitoring agent."""
    # Load configuration
    with open('workflow_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Add SQLite path and disable isolation
    config['configurable']['db_connection_string'] = 'workflow_history.db'
    config['configurable']['use_isolation'] = False
    
    # Create workflow state
    state = {
        "action": "remove",
        "target_name": "monitoring_agent",
        "integration_type": "infra_agent",
        "parameters": {}
    }
    
    # Create agent config
    agent_config = WorkflowAgentConfig(
        max_concurrent_tasks=5,
        use_isolation=False,
        isolation_method="direct",
        execution_timeout=30000,
        skip_verification=False,
        use_llm_optimization=False,
        rule_based_optimization=True,
        use_static_analysis=True
    )
    
    # Create and initialize agent
    agent = WorkflowAgent(config=agent_config)
    await agent.initialize(config)
    
    try:
        # Execute workflow
        result = await agent.invoke(state, config)
        print("\nRemoval Result:")
        print(f"Success: {'error' not in result}")
        if 'error' in result:
            print(f"Error: {result['error']}")
        if 'output' in result:
            print(f"Output: {result['output']}")
    finally:
        await agent.cleanup()

async def test_verify_monitoring_agent():
    """Test verifying a monitoring agent installation."""
    # Load configuration
    with open('workflow_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Add SQLite path and disable isolation
    config['configurable']['db_connection_string'] = 'workflow_history.db'
    config['configurable']['use_isolation'] = False
    
    # Create workflow state
    state = {
        "action": "verify",
        "target_name": "monitoring_agent",
        "integration_type": "infra_agent",
        "parameters": {}
    }
    
    # Create agent config
    agent_config = WorkflowAgentConfig(
        max_concurrent_tasks=5,
        use_isolation=False,
        isolation_method="direct",
        execution_timeout=30000,
        skip_verification=False,
        use_llm_optimization=False,
        rule_based_optimization=True,
        use_static_analysis=True
    )
    
    # Create and initialize agent
    agent = WorkflowAgent(config=agent_config)
    await agent.initialize(config)
    
    try:
        # Execute workflow
        result = await agent.invoke(state, config)
        print("\nVerification Result:")
        print(f"Success: {'error' not in result}")
        if 'error' in result:
            print(f"Error: {result['error']}")
        if 'verification_output' in result:
            print(f"Verification Output: {result['verification_output']}")
    finally:
        await agent.cleanup()

async def main():
    """Run all test scenarios."""
    print("Starting workflow agent tests...")
    
    # Test installation
    print("\nTesting installation scenario...")
    await test_install_monitoring_agent()
    
    # Test verification
    print("\nTesting verification scenario...")
    await test_verify_monitoring_agent()
    
    # Test removal
    print("\nTesting removal scenario...")
    await test_remove_monitoring_agent()
    
    print("\nAll tests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 