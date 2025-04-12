"""
Enhanced workflow test script that demonstrates the improved components working together.
This script shows:
1. The WorkflowTracker for state management
2. The TemplateManager with conditional templates
3. The KnowledgeBase with caching
4. The RecoverySystem for error handling
"""
import sys
import os
import logging
import asyncio
import json
import argparse
from pathlib import Path
import uuid

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflow_agent.multi_agent.workflow_tracker import WorkflowTracker
from src.workflow_agent.multi_agent.recovery import WorkflowRecovery, RecoveryStrategy
from src.workflow_agent.templates.manager import TemplateManager
from src.workflow_agent.templates.conditional import ConditionalTemplateRenderer
from src.workflow_agent.storage.knowledge_base import KnowledgeBase
from src.workflow_agent.core.state import WorkflowState
from src.workflow_agent.execution.executor import ScriptExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enhanced_workflow.log')
    ]
)
logger = logging.getLogger(__name__)

class EnhancedWorkflowRunner:
    """
    Enhanced workflow runner that uses all the improved components.
    """
    
    def __init__(self, 
                 integration_type: str = "infra_agent", 
                 action: str = "install",
                 license_key: str = "test-license",
                 use_tracker: bool = True):
        """
        Initialize enhanced workflow runner.
        
        Args:
            integration_type: Type of integration
            action: Action to perform
            license_key: License key
            use_tracker: Whether to use the workflow tracker
        """
        self.integration_type = integration_type
        self.action = action
        self.license_key = license_key
        self.use_tracker = use_tracker
        
        # Create a unique workflow ID
        self.workflow_id = str(uuid.uuid4())
        
        # Initialize components
        template_dirs = [
            os.path.join(Path(__file__).parent.parent, "templates"),
        ]
        self.template_manager = TemplateManager(template_dirs=template_dirs)
        self.template_renderer = ConditionalTemplateRenderer(self.template_manager)
        
        self.knowledge_base = KnowledgeBase()
        self.workflow_tracker = WorkflowTracker() if use_tracker else None
        self.recovery = WorkflowRecovery(coordinator=None)
        self.executor = ScriptExecutor(config={
            "isolation_method": "direct",
            "execution_timeout": 300,
            "security": {
                "least_privilege_execution": False,
                "use_docker_isolation": False
            }
        })
        
        # Initialize state
        self.state = WorkflowState(
            transaction_id=self.workflow_id,
            integration_type=integration_type,
            target_name=self.integration_type,
            action=action,
            parameters={
                "license_key": license_key,
                "host": "localhost",
                "port": "8080",
                "install_dir": r"C:\Users\hi\EnhancedTest" if os.name == 'nt' else "/tmp/enhancedtest",
                "config_path": r"C:\Users\hi\EnhancedTest\config" if os.name == 'nt' else "/tmp/enhancedtest/config",
                "log_path": r"C:\Users\hi\EnhancedTest\logs" if os.name == 'nt' else "/tmp/enhancedtest/logs"
            },
            system_context={
                "is_windows": os.name == 'nt',
                "platform": {
                    "system": "Windows" if os.name == 'nt' else "Linux"
                }
            }
        )
    
    async def initialize(self):
        """Initialize all components."""
        logger.info(f"Initializing enhanced workflow runner for {self.integration_type}/{self.action}")
        
        # Initialize knowledge base
        await self.knowledge_base.initialize()
        
        # Create workflow if using tracker
        if self.workflow_tracker:
            await self.workflow_tracker.create_workflow(self.workflow_id, self.state.model_dump())
            await self.workflow_tracker.create_checkpoint(self.workflow_id, "initial")
    
    async def run(self):
        """
        Run the workflow with all enhanced components.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Retrieve knowledge
            logger.info("Step 1: Retrieving knowledge")
            knowledge_step = await self.run_knowledge_step()
            if not knowledge_step["success"]:
                logger.error(f"Knowledge step failed: {knowledge_step.get('error', 'Unknown error')}")
                return False
                
            # Update state
            if self.workflow_tracker:
                await self.workflow_tracker.update_workflow(self.workflow_id, self.state.model_dump(), "knowledge_retrieved")
                await self.workflow_tracker.create_checkpoint(self.workflow_id, "after_knowledge")
                
            # Step 2: Generate script
            logger.info("Step 2: Generating script")
            script_step = await self.run_script_step()
            if not script_step["success"]:
                logger.error(f"Script generation step failed: {script_step.get('error', 'Unknown error')}")
                return False
                
            # Update state
            if self.workflow_tracker:
                await self.workflow_tracker.update_workflow(self.workflow_id, self.state.model_dump(), "script_generated")
                await self.workflow_tracker.create_checkpoint(self.workflow_id, "after_script_generation")
                
            # Step 3: Execute script
            logger.info("Step 3: Executing script")
            execution_step = await self.run_execution_step()
            if not execution_step["success"]:
                logger.error(f"Execution step failed: {execution_step.get('error', 'Unknown error')}")
                
                # Try recovery
                logger.info("Attempting recovery")
                recovery_result = await self.recovery.handle_error(
                    self.workflow_id,
                    execution_step.get("error", "Execution failed"),
                    self.state.model_dump()
                )
                
                if recovery_result.get("success", False):
                    logger.info("Recovery successful")
                else:
                    logger.error(f"Recovery failed: {recovery_result.get('error', 'Unknown error')}")
                    return False
            
            # Update state
            if self.workflow_tracker:
                await self.workflow_tracker.update_workflow(self.workflow_id, self.state.model_dump(), "script_executed")
                await self.workflow_tracker.create_checkpoint(self.workflow_id, "after_execution")
                
            logger.info("Workflow completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error during workflow execution: {e}", exc_info=True)
            return False
            
    async def run_knowledge_step(self):
        """
        Run the knowledge retrieval step.
        
        Returns:
            Step result
        """
        try:
            # Check if knowledge exists
            docs = await self.knowledge_base.retrieve_documents(
                self.integration_type,
                self.state.target_name,
                self.action
            )
            
            # If no knowledge, create sample knowledge
            if not docs or "definition" not in docs:
                logger.info(f"No knowledge found for {self.integration_type}, creating sample knowledge")
                
                # Create sample definition
                definition = {
                    "name": f"{self.integration_type} Agent",
                    "description": "Agent for monitoring system metrics",
                    "version": "1.0.0",
                    "parameters": [
                        {
                            "name": "license_key",
                            "description": "License key",
                            "required": True,
                            "type": "string"
                        },
                        {
                            "name": "host",
                            "description": "Host to monitor",
                            "required": True,
                            "type": "string",
                            "default": "localhost"
                        },
                        {
                            "name": "port",
                            "description": "Port to use",
                            "required": False,
                            "type": "integer",
                            "default": 8080
                        }
                    ]
                }
                
                # Add document
                success = await self.knowledge_base.add_document(
                    integration_type=self.integration_type,
                    target_name=self.state.target_name,
                    doc_type="definition",
                    content=definition,
                    source="enhanced_workflow_test"
                )
                
                if success:
                    logger.info(f"Added knowledge for {self.integration_type}")
                    docs = {"definition": definition}
                else:
                    logger.error(f"Failed to add knowledge for {self.integration_type}")
                    return {"success": False, "error": "Failed to add knowledge"}
            
            # Update state with knowledge
            self.state = self.state.copy(update={"template_data": {"knowledge": docs.get("definition", {})}})
            
            return {"success": True, "knowledge": docs}
            
        except Exception as e:
            logger.error(f"Error in knowledge step: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def run_script_step(self):
        """
        Run the script generation step.
        
        Returns:
            Step result
        """
        try:
            # Create context for rendering
            context = {
                "parameters": self.state.parameters,
                "action": self.state.action,
                "integration_type": self.state.integration_type,
                "target_name": self.state.target_name,
                "system_context": self.state.system_context,
                "knowledge": self.state.template_data.get("knowledge", {}) if self.state.template_data else {}
            }
            
            # Render template
            render_result = await self.template_renderer.render_template(
                self.action,
                self.integration_type,
                context
            )
            
            if not render_result["success"]:
                logger.warning(f"Failed to render template: {render_result.get('error', 'Unknown error')}")
                
                # Create a simple fallback script
                is_windows = self.state.system_context.get("is_windows", os.name == 'nt')
                script = self._create_fallback_script(is_windows)
                
                # Update state
                self.state = self.state.copy(update={"script": script})
                
                return {"success": True, "script": script, "fallback": True}
            
            # Update state with script
            self.state = self.state.copy(update={"script": render_result["rendered"]})
            
            return {"success": True, "script": render_result["rendered"], "template_path": render_result["template_path"]}
            
        except Exception as e:
            logger.error(f"Error in script step: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _create_fallback_script(self, is_windows: bool):
        """
        Create a fallback script when template rendering fails.
        
        Args:
            is_windows: Whether to create a Windows or Unix script
            
        Returns:
            Fallback script
        """
        if is_windows:
            # PowerShell fallback script
            install_dir = self.state.parameters.get('install_dir', 'C:\\EnhancedTest')
            config_path = self.state.parameters.get('config_path', 'C:\\EnhancedTest\\config')
            log_path = self.state.parameters.get('log_path', 'C:\\EnhancedTest\\logs')
            
            return f"""
# Fallback script for {self.integration_type} {self.action}
$ErrorActionPreference = "Stop"

# Parameters
$LicenseKey = "{self.state.parameters.get('license_key', 'test-license')}"
$Host = "{self.state.parameters.get('host', 'localhost')}"
$InstallDir = "{install_dir}"
$ConfigPath = "{config_path}"
$LogPath = "{log_path}"

Write-Host "Installing {self.state.target_name}"
Write-Host "Integration type: {self.integration_type}"
Write-Host "License Key: $LicenseKey"
Write-Host "Host: $Host"

# Create directories
New-Item -ItemType Directory -Force -Path "$InstallDir" | Out-Null
New-Item -ItemType Directory -Force -Path "$ConfigPath" | Out-Null
New-Item -ItemType Directory -Force -Path "$LogPath" | Out-Null

# Write configuration
$config = @{{
    "license_key" = "$LicenseKey"
    "host" = "$Host"
    "log_level" = "INFO"
}} | ConvertTo-Json

Set-Content -Path "$ConfigPath\\config.json" -Value $config

Write-Host "CHANGE_JSON_BEGIN"
Write-Host "@{{
  \\"type\\": \\"file_create\\",
  \\"target\\": \\"$ConfigPath\\\\config.json\\",
  \\"revertible\\": true,
  \\"backup_file\\": null
}}"
Write-Host "CHANGE_JSON_END"

Write-Host "CHANGE_JSON_BEGIN"
Write-Host "@{{
  \\"type\\": \\"directory_create\\",
  \\"target\\": \\"$InstallDir\\",
  \\"revertible\\": true,
  \\"backup_file\\": null
}}"
Write-Host "CHANGE_JSON_END"

Write-Host "{self.state.target_name} installed successfully"
exit 0
"""
        else:
            # Bash fallback script
            install_dir = self.state.parameters.get('install_dir', '/tmp/enhancedtest')
            config_path = self.state.parameters.get('config_path', '/tmp/enhancedtest/config')
            log_path = self.state.parameters.get('log_path', '/tmp/enhancedtest/logs')
            
            return f"""
#!/bin/bash
# Fallback script for {self.integration_type} {self.action}
set -e

# Parameters
LICENSE_KEY="{self.state.parameters.get('license_key', 'test-license')}"
HOST="{self.state.parameters.get('host', 'localhost')}"
INSTALL_DIR="{install_dir}"
CONFIG_PATH="{config_path}"
LOG_PATH="{log_path}"

echo "Installing {self.state.target_name}"
echo "Integration type: {self.integration_type}"
echo "License Key: $LICENSE_KEY"
echo "Host: $HOST"

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_PATH"
mkdir -p "$LOG_PATH"

# Write configuration
cat > "$CONFIG_PATH/config.json" << EOF
{{
  "license_key": "$LICENSE_KEY",
  "host": "$HOST",
  "log_level": "INFO"
}}
EOF

# Track changes
echo "CHANGE_JSON_BEGIN"
echo "{{
  \\"type\\": \\"file_create\\",
  \\"target\\": \\"$CONFIG_PATH/config.json\\",
  \\"revertible\\": true,
  \\"backup_file\\": null
}}"
echo "CHANGE_JSON_END"

echo "CHANGE_JSON_BEGIN"
echo "{{
  \\"type\\": \\"directory_create\\",
  \\"target\\": \\"$INSTALL_DIR\\",
  \\"revertible\\": true,
  \\"backup_file\\": null
}}"
echo "CHANGE_JSON_END"

echo "{self.state.target_name} installed successfully"
exit 0
"""
    
    async def run_execution_step(self):
        """
        Run the script execution step.
        
        Returns:
            Step result
        """
        try:
            # Execute script
            execution_result = await self.executor.execute(self.state)
            
            if "error" in execution_result:
                logger.error(f"Script execution failed: {execution_result['error']}")
                return {"success": False, "error": execution_result["error"]}
                
            # Update state with execution results
            state_update = {}
            if "output" in execution_result:
                state_update["output"] = execution_result["output"]
            if "changes" in execution_result:
                state_update["changes"] = execution_result["changes"]
                
            self.state = self.state.copy(update=state_update)
            
            return {"success": True, "output": execution_result.get("output", "")}
            
        except Exception as e:
            logger.error(f"Error in execution step: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def cleanup(self):
        """Clean up resources."""
        if self.workflow_tracker:
            # Set final status
            try:
                await self.workflow_tracker.set_workflow_status(
                    self.workflow_id, 
                    "completed" if self.state.error is None else "failed"
                )
            except Exception as e:
                logger.warning(f"Error setting final workflow status: {e}")

async def main():
    """Run the enhanced workflow test."""
    parser = argparse.ArgumentParser(description="Enhanced workflow test")
    parser.add_argument("--action", default="install", choices=["install", "remove", "verify"], help="Action to perform")
    parser.add_argument("--integration", default="infra_agent", help="Integration type")
    parser.add_argument("--license", default="test-license", help="License key")
    parser.add_argument("--no-tracker", action="store_true", help="Disable workflow tracker")
    args = parser.parse_args()
    
    logger.info(f"Starting enhanced workflow test for {args.integration}/{args.action}")
    
    runner = EnhancedWorkflowRunner(
        integration_type=args.integration,
        action=args.action,
        license_key=args.license,
        use_tracker=not args.no_tracker
    )
    
    try:
        # Initialize
        await runner.initialize()
        
        # Run the workflow
        success = await runner.run()
        
        # Cleanup
        await runner.cleanup()
        
        if success:
            logger.info(f"Workflow {args.action} completed successfully!")
            return 0
        else:
            logger.error(f"Workflow {args.action} failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
