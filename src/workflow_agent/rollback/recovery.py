import os
import uuid
import tempfile
import subprocess
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from jinja2 import Template
from ..core.state import WorkflowState, OutputData, ExecutionMetrics, Change
from ..config.templates import script_templates
from ..config.configuration import ensure_workflow_config
from ..storage import HistoryManager
from ..error.exceptions import ExecutionError, RollbackError
from datetime import datetime

logger = logging.getLogger(__name__)

class RecoveryManager:
    """Manages workflow rollback and recovery operations."""
    
    def __init__(self, history_manager: HistoryManager):
        self.history_manager = history_manager
        self._rollback_scripts: Dict[str, str] = {}
        self._rollback_status: Dict[str, bool] = {}
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the recovery manager with configuration."""
        try:
            # Ensure config is a dict
            config = ensure_workflow_config(config)
            
            # Initialize history manager if needed
            if not self.history_manager:
                self.history_manager = HistoryManager()
            
            # Initialize any additional resources based on config
            logger.info("RecoveryManager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RecoveryManager: {e}")
            raise
    
    async def prepare_rollback(self, 
                             transaction_id: str,
                             changes: List[Dict[str, Any]],
                             context: Optional[Dict[str, Any]] = None) -> bool:
        """Prepare rollback scripts for changes."""
        try:
            # Generate rollback scripts for each change
            for change in changes:
                rollback_script = await self._generate_rollback_script(change, context)
                if rollback_script:
                    self._rollback_scripts[f"{transaction_id}_{change['id']}"] = rollback_script
                    self._rollback_status[f"{transaction_id}_{change['id']}"] = False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to prepare rollback for transaction {transaction_id}: {e}")
            return False
    
    async def _generate_rollback_script(self, 
                                      change: Dict[str, Any],
                                      context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate a rollback script for a specific change."""
        try:
            # Get rollback template
            template_name = f"rollback_{change['type']}.sh"
            template_path = os.path.join("templates", "rollback", template_name)
            
            if not os.path.exists(template_path):
                # Generate basic rollback script if template doesn't exist
                return self._generate_basic_rollback(change)
            
            # Load and render template
            with open(template_path, "r") as f:
                template = f.read()
            
            # Prepare context
            template_context = {
                "change": change,
                "context": context or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Render template
            script = Template(template).render(**template_context)
            
            return script
            
        except Exception as e:
            logger.error(f"Failed to generate rollback script for change {change['id']}: {e}")
            return None
    
    def _generate_basic_rollback(self, change: Dict[str, Any]) -> str:
        """Generate a basic rollback script when no template exists."""
        script_lines = []
        
        if change["type"] == "file_modification":
            # Backup and restore file
            script_lines.extend([
                f"# Backup file: {change['target']}",
                f"cp {change['target']} {change['target']}.bak",
                f"# Restore original content",
                f"cat > {change['target']} << 'EOL'",
                change.get("original_content", ""),
                "EOL"
            ])
        
        elif change["type"] == "command_execution":
            # Execute reverse command if available
            if "reverse_command" in change:
                script_lines.append(f"# Execute reverse command: {change['reverse_command']}")
                script_lines.append(change["reverse_command"])
        
        return "\n".join(script_lines)
    
    async def execute_rollback(self, transaction_id: str) -> bool:
        """Execute rollback scripts for a transaction."""
        success = True
        
        try:
            # Get all rollback scripts for this transaction
            rollback_keys = [k for k in self._rollback_scripts.keys() if k.startswith(transaction_id)]
            
            for key in rollback_keys:
                if not self._rollback_status[key]:
                    script = self._rollback_scripts[key]
                    
                    # Execute rollback script
                    try:
                        process = await asyncio.create_subprocess_shell(
                            script,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        stdout, stderr = await process.communicate()
                        
                        if process.returncode != 0:
                            logger.error(f"Rollback script failed: {stderr.decode()}")
                            success = False
                        else:
                            self._rollback_status[key] = True
                            logger.info(f"Rollback script executed successfully: {key}")
                            
                    except Exception as e:
                        logger.error(f"Error executing rollback script {key}: {e}")
                        success = False
            
            # Record rollback result
            await self.history_manager.record_execution({
                "transaction_id": transaction_id,
                "action": "rollback",
                "target_name": "workflow",
                "parameters": {"rollback_keys": rollback_keys},
                "result": {
                    "success": success,
                    "status": self._rollback_status
                }
            })
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to execute rollback for transaction {transaction_id}: {e}")
            return False
    
    async def cleanup(self) -> None:
        """Clean up rollback resources."""
        try:
            self._rollback_scripts.clear()
            self._rollback_status.clear()
            logger.info("Rollback resources cleaned up")
        except Exception as e:
            logger.error(f"Error during rollback cleanup: {e}")
            # Don't re-raise as cleanup should be best-effort