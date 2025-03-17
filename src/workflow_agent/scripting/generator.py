# src/workflow_agent/scripting/generator.py
import logging
import uuid
import time
from typing import Dict, Any, Optional, List
from jinja2 import Template
from pathlib import Path
from ..core.state import WorkflowState, Change
from ..config.templates import script_templates
from ..storage import HistoryManager
from ..utils.system import get_system_context
from ..integrations import IntegrationHandler
from .optimizers import get_optimizer

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """Generates scripts based on templates or integrations with optional optimization."""
    
    def __init__(self, history_manager: Optional[HistoryManager] = None):
        """
        Initialize the script generator.
        
        Args:
            history_manager: Optional history manager for retrieving execution history
        """
        self.history_manager = history_manager or HistoryManager()
        self.integration_handler = IntegrationHandler()
    
    async def generate_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a script for the requested integration.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state or error message
        """
        system_context = get_system_context()
        
        # Store system context in result
        result = {"system_context": system_context}
        
        # Check for custom template
        template_str = None
        if config and "configurable" in config and config["configurable"].get("custom_template_dir"):
            custom_template_dir = config["configurable"]["custom_template_dir"]
            custom_template_file = Path(custom_template_dir) / f"{state.target_name}-{state.action}.sh.j2"
            if custom_template_file.exists():
                logger.info(f"Using custom template from {custom_template_file}")
                try:
                    with open(custom_template_file, "r") as f:
                        template_str = f.read()
                    result["script_source"] = "custom_template"
                except Exception as e:
                    logger.error(f"Error reading custom template: {e}")
                    template_str = None
        
        # Route to specialized handler if not an infra_agent integration
        if state.integration_type != "infra_agent":
            logger.info(f"Routing to specialized handler for {state.integration_type}")
            handler_result = await self.integration_handler.handle_integration(state, config)
            
            if "error" in handler_result:
                return handler_result
            
            result.update(handler_result)
            result["system_context"] = system_context
            return result
        
        # For infra_agent integrations, try template-based generation first
        if not template_str:  # If no custom template was found
            template_key = state.template_key or f"{state.target_name}-{state.action}"
            template_str = script_templates.get(template_key)
            
            # If specific template not found, try the default template
            if not template_str:
                template_key = f"default-{state.action}"
                template_str = script_templates.get(template_key)
                if template_str:
                    logger.info(f"Using default template for action '{state.action}'")
                    result["script_source"] = "default_template"
        
        # Get execution history and stats for potential optimization
        history = []
        stats = {}
        if self.history_manager:
            history = await self.history_manager.get_execution_history(state.target_name, state.action, limit=10)
            stats = await self.history_manager.get_execution_statistics(state.target_name, state.action)
        
        # Store history in result
        result["history"] = history
        
        if template_str:
            try:
                # First, render the template
                try:
                    tpl = Template(template_str)
                    script = tpl.render(
                        action=state.action,
                        target_name=state.target_name,
                        parameters=state.parameters
                    )
                    result["script_source"] = "template"
                except Exception as e:
                    logger.error(f"Template rendering failed: {e}")
                    return {"error": f"Template rendering failed: {str(e)}"}
                
                # Then, optimize if requested and available
                if state.optimized and config and "configurable" in config:
                    optimizer_name = None
                    if config["configurable"].get("use_llm_optimization"):
                        optimizer_name = "llm"
                    elif config["configurable"].get("rule_based_optimization"):
                        optimizer_name = "rule-based"
                    elif config["configurable"].get("use_static_analysis"):
                        optimizer_name = "shellcheck"
                    
                    if optimizer_name:
                        optimizer = get_optimizer(optimizer_name)
                        if optimizer:
                            try:
                                logger.info(f"Attempting script optimization using {optimizer_name}")
                                optimized_script = await optimizer(script, state, system_context, history, stats)
                                
                                # Verify the optimized script is valid
                                if optimized_script and len(optimized_script) > 10:  # Simple sanity check
                                    script = optimized_script
                                    result["script_source"] = f"optimized_{optimizer_name}"
                                    result["optimized"] = True
                                else:
                                    logger.warning(f"{optimizer_name} optimization returned invalid script, using original")
                            except Exception as e:
                                logger.error(f"Script optimization failed: {e}")
                                # Continue with unoptimized script
                
                # Parse script to identify changes it will make
                changes = await self._extract_changes_from_script(script, state)
                
                logger.info(f"Script generated successfully from {result['script_source']}")
                
                # Add script and changes to result
                result["script"] = script
                result["changes"] = changes
                
                # For backward compatibility
                result["legacy_changes"] = [change.details for change in changes]
                
                # Add metrics start time
                result["metrics"] = {"start_time": time.time()}
                
                return result
            except Exception as e:
                logger.error(f"Script generation failed: {e}")
        
        # Fallback to docs-based generation using integration handler
        try:
            logger.info("No suitable template found, falling back to documentation-based generation")
            handler_result = await self.integration_handler.handle_infra_agent(state, config)
            
            if "error" not in handler_result:
                handler_result["system_context"] = system_context
                
                # If no changes provided, add a generic one
                if "changes" not in handler_result:
                    changes = [Change(
                        type=state.action,
                        target=state.target_name,
                        details=f"{state.action.capitalize()} {state.target_name}",
                        revertible=True
                    )]
                    handler_result["changes"] = changes
                    handler_result["legacy_changes"] = [change.details for change in changes]
            
            return handler_result
        except Exception as err:
            logger.error(f"Script generation failed: {err}")
            return {"error": f"Script generation failed: {str(err)}"}
    
    async def _extract_changes_from_script(self, script: str, state: WorkflowState) -> List[Change]:
        """
        Extract system changes from a script.
        
        Args:
            script: Script content
            state: Current workflow state
            
        Returns:
            List of Change objects
        """
        changes = []
        
        # Extract changes based on script content
        if state.action == "install":
            # Look for package installations
            for line in script.split("\n"):
                if "apt-get install" in line or "yum install" in line:
                    parts = line.split("install")
                    if len(parts) > 1:
                        packages = parts[1].strip().split()
                        for pkg in packages:
                            if pkg not in ["-y", "--yes", "-q", "--quiet"]:
                                changes.append(Change(
                                    type="install",
                                    target=f"package:{pkg}",
                                    details=f"Install package: {pkg}",
                                    revertible=True,
                                    revert_command=f"apt-get remove -y {pkg} || yum remove -y {pkg}"
                                ))
                
                # Look for file creation
                elif ">" in line and not line.strip().startswith("#"):
                    parts = line.split(">")
                    if len(parts) > 1:
                        file_path = parts[1].strip().split()[0]
                        if file_path and file_path[0] == "/":
                            changes.append(Change(
                                type="modify",
                                target=f"file:{file_path}",
                                details=f"Create or modify file: {file_path}",
                                revertible=True,
                                revert_command=f"rm -f {file_path}"
                            ))
                
                # Look for service configurations
                elif "systemctl enable" in line or "systemctl start" in line:
                    parts = line.split("systemctl")
                    if len(parts) > 1:
                        action_service = parts[1].strip().split()
                        if len(action_service) >= 2:
                            service = action_service[1]
                            changes.append(Change(
                                type="configure",
                                target=f"service:{service}",
                                details=f"Configure service: {service}",
                                revertible=True,
                                revert_command=f"systemctl stop {service} && systemctl disable {service}"
                            ))
        
        elif state.action == "remove":
            for line in script.split("\n"):
                if "apt-get remove" in line or "yum remove" in line:
                    parts = line.split("remove")
                    if len(parts) > 1:
                        packages = parts[1].strip().split()
                        for pkg in packages:
                            if pkg not in ["-y", "--yes", "-q", "--quiet"]:
                                changes.append(Change(
                                    type="remove",
                                    target=f"package:{pkg}",
                                    details=f"Remove package: {pkg}",
                                    revertible=False
                                ))
                
                elif "rm" in line and not line.strip().startswith("#"):
                    parts = line.split("rm")
                    if len(parts) > 1:
                        file_paths = parts[1].strip().split()
                        for file_path in file_paths:
                            if file_path not in ["-f", "-r", "-rf", "--force"]:
                                changes.append(Change(
                                    type="remove",
                                    target=f"file:{file_path}",
                                    details=f"Remove file: {file_path}",
                                    revertible=False
                                ))
        
        # Add generic change if none were detected
        if not changes:
            changes.append(Change(
                type=state.action,
                target=state.target_name,
                details=f"{state.action.capitalize()} {state.target_name}",
                revertible=True
            ))
        
        return changes