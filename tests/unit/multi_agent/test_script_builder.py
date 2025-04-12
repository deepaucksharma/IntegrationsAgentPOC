"""
Unit tests for the ScriptBuilderAgent implementation.
"""
import unittest
import asyncio
from unittest.mock import Mock, MagicMock, patch
import json

from src.workflow_agent.multi_agent.script_builder import ScriptBuilderAgent
from src.workflow_agent.multi_agent.interfaces import ScriptBuilderAgentInterface
from src.workflow_agent.multi_agent.base import MultiAgentMessage, MessageType
from src.workflow_agent.core.state import WorkflowState

class TestScriptBuilderAgent(unittest.TestCase):
    """Tests for ScriptBuilderAgent."""
    
    def setUp(self):
        """Set up test environment."""
        self.message_bus = MagicMock()
        self.coordinator = MagicMock()
        
        # Create agent instance
        self.agent = ScriptBuilderAgent(
            message_bus=self.message_bus,
            coordinator=self.coordinator
        )
        
        # Mock the generator and validator
        self.agent.generator = MagicMock()
        self.agent.validator = MagicMock()
        
        # Create a test workflow state
        self.state = WorkflowState(
            workflow_id="test-workflow",
            integration_type="test-integration",
            target_name="test-target",
            action="install",
            parameters={
                "install_dir": "/opt/test",
                "version": "1.0.0"
            },
            system_context={
                "is_windows": False,
                "platform": {
                    "system": "linux"
                },
                "package_managers": {
                    "apt": True
                }
            }
        )
    
    def test_interface_implementation(self):
        """Test that ScriptBuilderAgent implements the correct interface."""
        self.assertIsInstance(self.agent, ScriptBuilderAgentInterface)
    
    def test_initialization(self):
        """Test agent initialization."""
        # Check that handlers are registered
        self.assertIn("generate_script", self.agent._message_handlers)
        self.assertIn("validate_script", self.agent._message_handlers)
    
    async def _test_generate_script(self):
        """Test script generation."""
        # Mock generator return value
        self.agent.generator.generate_script.return_value = {
            "script": "#!/bin/bash\necho 'Test script'",
            "template_key": "linux/install.sh.j2"
        }
        
        # Call the method
        result = await self.agent.generate_script(self.state, {})
        
        # Verify generator was called
        self.agent.generator.generate_script.assert_called_once()
        
        # Check result
        self.assertIn("script", result)
        self.assertIn("template_key", result)
        self.assertEqual(result["script"], "#!/bin/bash\necho 'Test script'")
    
    async def _test_validate_script(self):
        """Test script validation."""
        # Set script on state
        state_with_script = self.state.set_script("#!/bin/bash\necho 'Test script'")
        
        # Mock validator return value
        self.agent.validator.validate_script.return_value = {
            "valid": True,
            "warnings": ["Consider adding error handling"]
        }
        
        # Call the method
        result = await self.agent.validate_script(state_with_script, {})
        
        # Verify validator was called
        self.agent.validator.validate_script.assert_called_once()
        
        # Check result
        self.assertIn("valid", result)
        self.assertIn("warnings", result)
        self.assertTrue(result["valid"])
    
    async def _test_optimize_script(self):
        """Test script optimization."""
        # Set script on state
        state_with_script = self.state.set_script("#!/bin/bash\necho 'Test script'")
        
        # Call the method
        result = await self.agent.optimize_script(state_with_script, {
            "platform": {
                "system": "linux"
            },
            "package_managers": {
                "apt": True
            }
        })
        
        # Check result
        self.assertIn("optimized", result)
        self.assertIn("script", result)
        self.assertTrue(result["optimized"])
    
    async def _test_handle_message(self):
        """Test message handling."""
        # Create a test message
        message = MultiAgentMessage(
            sender="TestAgent",
            message_type="generate_script",
            content={
                "state": self.state.model_dump(),
                "config": {}
            }
        )
        
        # Mock generate_script method
        self.agent.generate_script = MagicMock()
        self.agent.generate_script.return_value = {
            "script": "#!/bin/bash\necho 'Test script'",
            "template_key": "linux/install.sh.j2"
        }
        
        # Call message handler
        await self.agent._handle_message(message)
        
        # Verify generate_script was called
        self.agent.generate_script.assert_called_once()
        
        # Verify response was sent
        self.coordinator.route_message.assert_called_once()
    
    def test_async_methods(self):
        """Run async tests."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._test_generate_script())
        loop.run_until_complete(self._test_validate_script())
        loop.run_until_complete(self._test_optimize_script())
        loop.run_until_complete(self._test_handle_message())

if __name__ == '__main__':
    unittest.main()
