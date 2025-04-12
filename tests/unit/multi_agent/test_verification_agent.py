"""
Unit tests for the VerificationAgent implementation.
"""
import unittest
import asyncio
from unittest.mock import Mock, MagicMock, patch
import json
from datetime import datetime

from src.workflow_agent.multi_agent.verification import VerificationAgent, VerificationStep
from src.workflow_agent.multi_agent.interfaces import VerificationAgentInterface
from src.workflow_agent.multi_agent.base import MultiAgentMessage, MessageType
from src.workflow_agent.core.state import WorkflowState, WorkflowStatus

class TestVerificationAgent(unittest.TestCase):
    """Tests for VerificationAgent."""
    
    def setUp(self):
        """Set up test environment."""
        self.message_bus = MagicMock()
        self.coordinator = MagicMock()
        
        # Create agent instance
        self.agent = VerificationAgent(
            message_bus=self.message_bus,
            coordinator=self.coordinator
        )
        
        # Mock the executor
        self.agent.executor = MagicMock()
        
        # Create a test workflow state
        self.state = WorkflowState(
            workflow_id="test-workflow",
            integration_type="test-integration",
            target_name="test-target",
            action="install",
            parameters={
                "install_dir": "/opt/test",
                "config_path": "/etc/test/config.conf"
            },
            system_context={
                "is_windows": False,
                "platform": {
                    "system": "linux"
                }
            },
            verification_data={
                "steps": [
                    {
                        "name": "Check Process",
                        "description": "Check if the process is running",
                        "script": "ps -ef | grep test | grep -v grep",
                        "required": True
                    }
                ]
            }
        )
    
    def test_interface_implementation(self):
        """Test that VerificationAgent implements the correct interface."""
        self.assertIsInstance(self.agent, VerificationAgentInterface)
    
    def test_initialization(self):
        """Test agent initialization."""
        # Check that handlers are registered
        self.assertIn("verify_integration", self.agent._message_handlers)
        self.assertIn("verify_system_state", self.agent._message_handlers)
    
    def test_verification_step(self):
        """Test VerificationStep class."""
        step = VerificationStep(
            name="Test Step",
            description="Test description",
            script="echo 'test'",
            expected_result="test",
            required=True,
            timeout_seconds=30
        )
        
        # Test to_dict method
        step_dict = step.to_dict()
        self.assertEqual(step_dict["name"], "Test Step")
        self.assertEqual(step_dict["description"], "Test description")
        self.assertEqual(step_dict["script"], "echo 'test'")
        self.assertEqual(step_dict["expected_result"], "test")
        self.assertTrue(step_dict["required"])
        self.assertEqual(step_dict["timeout_seconds"], 30)
    
    async def _test_verify_execution(self):
        """Test execution verification."""
        # Test execution result
        execution_result = {
            "command": "echo 'test'",
            "exit_code": 0,
            "output": {
                "stdout": "test\n",
                "stderr": ""
            }
        }
        
        # Test context
        context = {
            "expected_exit_code": 0,
            "expected_output": "test"
        }
        
        # Call the method
        result = await self.agent.verify_execution(execution_result, context)
        
        # Check result
        self.assertIn("passed", result)
        self.assertTrue(result["passed"])
        self.assertTrue(result["exit_code_match"])
        self.assertTrue(result["output_match"])
        
        # Test with failing exit code
        execution_result["exit_code"] = 1
        result = await self.agent.verify_execution(execution_result, context)
        self.assertFalse(result["passed"])
        self.assertFalse(result["exit_code_match"])
        
        # Test with missing output
        execution_result["exit_code"] = 0
        execution_result["output"]["stdout"] = "wrong output"
        result = await self.agent.verify_execution(execution_result, context)
        self.assertFalse(result["passed"])
        self.assertTrue(result["exit_code_match"])
        self.assertFalse(result["output_match"])
    
    async def _test_verify_system_state(self):
        """Test system state verification."""
        # Mock executor response for successful verification
        mock_output = MagicMock()
        mock_output.stdout = "Directory exists"
        
        mock_result_state = MagicMock()
        mock_result_state.has_error = False
        mock_result_state.output = mock_output
        
        self.agent.executor.execute.return_value = mock_result_state
        
        # Call the method
        result = await self.agent.verify_system_state(self.state)
        
        # Check result
        self.assertIn("passed", result)
        self.assertTrue(result["passed"])
        self.assertIn("passed_steps", result)
        self.assertGreaterEqual(len(result["passed_steps"]), 1)
        
        # Test with failing step
        mock_result_state.has_error = True
        mock_result_state.error = "Command failed"
        
        # Replace return value with error state
        self.agent.executor.execute.return_value = mock_result_state
        
        # Call the method again
        result = await self.agent.verify_system_state(self.state)
        
        # Check result
        self.assertFalse(result["passed"])
        self.assertIn("failed_steps", result)
        self.assertGreaterEqual(len(result["failed_steps"]), 1)
    
    async def _test_verify_security(self):
        """Test security verification."""
        # Test with safe script
        safe_script = "#!/bin/bash\necho 'Hello World'\n"
        result = await self.agent.verify_security(safe_script, "script")
        
        # Check result
        self.assertIn("passed", result)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["security_issues"]), 0)
        
        # Test with dangerous script
        dangerous_script = "#!/bin/bash\nrm -rf /\n"
        result = await self.agent.verify_security(dangerous_script, "script")
        
        # Check result
        self.assertFalse(result["passed"])
        self.assertGreaterEqual(len(result["security_issues"]), 1)
        
        # Test with config containing sensitive data
        sensitive_config = "password=my_secret_password\n"
        result = await self.agent.verify_security(sensitive_config, "config")
        
        # Check result
        self.assertFalse(result["passed"])
        self.assertGreaterEqual(len(result["security_issues"]), 1)
    
    async def _test_generate_verification_steps(self):
        """Test verification step generation."""
        # Call the method
        steps = self.agent._generate_verification_steps(self.state)
        
        # Check result
        self.assertGreaterEqual(len(steps), 3)  # 2 built-in steps + 1 from verification_data
        
        # Check that steps include directory and file checks
        step_names = [step.name for step in steps]
        self.assertIn("Check Installation Directory", step_names)
        self.assertIn("Check Configuration File", step_names)
        self.assertIn("Check Process", step_names)
    
    async def _test_run_verification_step(self):
        """Test running a verification step."""
        # Create a test step
        step = VerificationStep(
            name="Test Step",
            description="Test description",
            script="echo 'test'",
            expected_result="test",
            required=True
        )
        
        # Mock executor response
        mock_output = MagicMock()
        mock_output.stdout = "test\n"
        
        mock_result_state = MagicMock()
        mock_result_state.has_error = False
        mock_result_state.output = mock_output
        
        self.agent.executor.execute.return_value = mock_result_state
        
        # Call the method
        result = await self.agent._run_verification_step(step, self.state)
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "test\n")
        
        # Test with failing step (output mismatch)
        mock_output.stdout = "wrong output\n"
        mock_result_state.output = mock_output
        
        result = await self.agent._run_verification_step(step, self.state)
        
        # Check result
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("Expected output", result["error"])
        
        # Test with execution error
        mock_result_state.has_error = True
        mock_result_state.error = "Command failed"
        
        result = await self.agent._run_verification_step(step, self.state)
        
        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Command failed")
    
    async def _test_handle_message(self):
        """Test message handling."""
        # Mock verify_system_state method
        self.agent.verify_system_state = MagicMock()
        self.agent.verify_system_state.return_value = {
            "passed": True,
            "passed_steps": [{"name": "Test Step"}],
            "failed_steps": [],
            "total_steps": 1,
            "success_rate": 1.0
        }
        
        # Create a verification request message
        message = MultiAgentMessage(
            sender="TestAgent",
            message_type="verification_request",
            content={
                "verification_type": "state",
                "state": self.state.model_dump()
            }
        )
        
        # Call the handler
        await self.agent._handle_message(message)
        
        # Verify verify_system_state was called
        self.agent.verify_system_state.assert_called_once()
        
        # Verify response was sent
        self.coordinator.route_message.assert_called_once()
        
        # Test with execution verification
        self.coordinator.route_message.reset_mock()
        self.agent.verify_execution = MagicMock()
        self.agent.verify_execution.return_value = {
            "passed": True,
            "exit_code_match": True,
            "output_match": True
        }
        
        # Create an execution verification message
        message = MultiAgentMessage(
            sender="TestAgent",
            message_type="verification_request",
            content={
                "verification_type": "execution",
                "execution_result": {"exit_code": 0},
                "context": {"expected_exit_code": 0}
            }
        )
        
        # Call the handler
        await self.agent._handle_message(message)
        
        # Verify verify_execution was called
        self.agent.verify_execution.assert_called_once()
        
        # Verify response was sent
        self.coordinator.route_message.assert_called_once()
    
    def test_async_methods(self):
        """Run async tests."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._test_verify_execution())
        loop.run_until_complete(self._test_verify_system_state())
        loop.run_until_complete(self._test_verify_security())
        loop.run_until_complete(self._test_generate_verification_steps())
        loop.run_until_complete(self._test_run_verification_step())
        loop.run_until_complete(self._test_handle_message())

if __name__ == '__main__':
    unittest.main()
