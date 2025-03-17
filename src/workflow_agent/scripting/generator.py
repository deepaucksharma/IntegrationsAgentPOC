# src/workflow_agent/scripting/generator.py
import logging
import uuid
import time
import os
import json
from typing import Dict, Any, Optional, List
from jinja2 import Template, Environment
from pathlib import Path
from ..core.state import WorkflowState, Change
from ..config.templates import get_template, render_template, get_template_categories
from ..storage import HistoryManager
from ..utils.system import get_system_context
from ..integrations import IntegrationHandler
from .optimizers import get_optimizer
from .template_helpers import compose_template

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """
    Generates scripts based on templates or integrations with optional optimization.
    Enhanced to support categorized templates and composition.
    """
    
    def __init__(self, history_manager: Optional[HistoryManager] = None):
        """
        Initialize the script generator.
        
        Args:
            history_manager: Optional history manager for retrieving execution history
        """
        self.history_manager = history_manager or HistoryManager()
        self.integration_handler = IntegrationHandler()
        self.template_cache = {}  # Cache for rendered templates
    
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
        
        # Determine integration category if not provided
        if not hasattr(state, 'integration_category') or not state.integration_category:
            state.integration_category = self._determine_category(state.target_name, state.integration_type)
        
        # Build template key based on category, target and action
        template_keys = self._get_candidate_template_keys(state)
        
        # Find the most specific template
        template_str = None
        template_key_used = None
        
        for key in template_keys:
            template_content = get_template(key)
            if template_content:
                template_str = template_content
                template_key_used = key
                break
        
        # Route to specialized handler if not an infra_agent integration
        if state.integration_type != "infra_agent" and not template_str:
            logger.info(f"Routing to specialized handler for {state.integration_type}")
            handler_result = await self.integration_handler.handle_integration(state, config)
            
            if "error" in handler_result:
                return handler_result
            
            result.update(handler_result)
            result["system_context"] = system_context
            return result
        
        # For infra_agent integrations, try template-based generation first
        if template_str:
            try:
                # Prepare rendering context
                render_context = self._prepare_render_context(state, system_context)
                
                # Render the template
                try:
                    script = render_template(template_key_used, render_context)
                    if not script:
                        raise ValueError(f"Template rendering returned empty result for {template_key_used}")
                    
                    result["script_source"] = f"template:{template_key_used}"
                except Exception as e:
                    logger.error(f"Template rendering failed: {e}")
                    return {"error": f"Template rendering failed: {str(e)}"}
                
                # Get execution history and stats for potential optimization
                history = []
                stats = {}
                if self.history_manager:
                    history = await self.history_manager.get_execution_history(state.target_name, state.action, limit=10)
                    stats = await self.history_manager.get_execution_statistics(state.target_name, state.action)
                
                # Store history in result
                result["history"] = history
                
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
                
                # Store used template key for reference
                result["template_key"] = template_key_used
                
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
        
        # Fallback to integration handler if no template found
        try:
            logger.info("No suitable template found, falling back to integration handler")
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
    
    def _determine_category(self, target_name: str, integration_type: str) -> str:
        """
        Determine the category for an integration.
        
        Args:
            target_name: Target name
            integration_type: Integration type
            
        Returns:
            Category name
        """
        # Simple mapping of common target types to categories
        target_to_category = {
            # Databases
            "postgres": "database",
            "mysql": "database",
            "mongodb": "database",
            "redis": "database",
            "cassandra": "database",
            "elasticsearch": "database",
            
            # Web servers
            "nginx": "webserver",
            "apache": "webserver",
            "iis": "webserver",
            
            # AWS services
            "aws": "aws",
            "ec2": "aws",
            "rds": "aws",
            "s3": "aws",
            "lambda": "aws",
            "dynamodb": "aws",
            
            # Azure services
            "azure": "azure",
            "azurerm": "azure",
            
            # GCP services
            "gcp": "gcp",
            "gce": "gcp",
            
            # Containers
            "docker": "container",
            "kubernetes": "container",
            "k8s": "container",
            
            # Networking
            "haproxy": "network",
            "varnish": "network",
            "f5": "network",
            
            # Monitoring
            "prometheus": "monitoring",
            "grafana": "monitoring",
            "datadog": "monitoring",
            
            # Security
            "vault": "security",
            "waf": "security",
        }
        
        # Integration type overrides target name for certain categories
        integration_type_to_category = {
            "aws": "aws",
            "azure": "azure",
            "gcp": "gcp",
            "infra_agent": None,  # Use target name
        }
        
        # Check for direct map from integration type
        if integration_type in integration_type_to_category and integration_type_to_category[integration_type]:
            return integration_type_to_category[integration_type]
        
        # Check for target name match
        for prefix, category in target_to_category.items():
            if target_name.startswith(prefix):
                return category
        
        # Default to "custom" category
        return "custom"
    
    def _get_candidate_template_keys(self, state: WorkflowState) -> List[str]:
        """
        Get a list of potential template keys to try, from most specific to least.
        
        Args:
            state: Current workflow state
            
        Returns:
            List of template keys to try
        """
        template_keys = []
        
        # Construct potential keys from most specific to least specific
        
        # 1. Category + target + action (most specific)
        if hasattr(state, 'integration_category') and state.integration_category:
            template_keys.append(f"{state.integration_category}/{state.target_name}-{state.action}")
        
        # 2. Target + action
        template_keys.append(f"{state.target_name}-{state.action}")
        
        # 3. Category + target + default action
        if hasattr(state, 'integration_category') and state.integration_category:
            template_keys.append(f"{state.integration_category}/{state.target_name}-default")
        
        # 4. Target + default action
        template_keys.append(f"{state.target_name}-default")
        
        # 5. Integration type + action
        template_keys.append(f"{state.integration_type}-{state.action}")
        
        # 6. Category + default action
        if hasattr(state, 'integration_category') and state.integration_category:
            template_keys.append(f"{state.integration_category}/default-{state.action}")
        
        # 7. Default action (least specific)
        template_keys.append(f"default-{state.action}")
        
        # 8. User specified key overrides all (if provided)
        if state.template_key:
            template_keys.insert(0, state.template_key)
        
        return template_keys
    
    def _prepare_render_context(self, state: WorkflowState, system_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare context dictionary for template rendering.
        
        Args:
            state: Current workflow state
            system_context: System context information
            
        Returns:
            Context dictionary for template rendering
        """
        # Basic context
        context = {
            "action": state.action,
            "target_name": state.target_name,
            "parameters": state.parameters or {},
            "integration_type": state.integration_type,
            "system": system_context,
            "transaction_id": state.transaction_id or str(uuid.uuid4()),
        }
        
        # Add integration_category if available
        if hasattr(state, 'integration_category') and state.integration_category:
            context["integration_category"] = state.integration_category
        
        # Add helper functions
        context["get_platform"] = lambda: system_context.get('platform', {}).get('system', 'unknown')
        context["is_linux"] = lambda: system_context.get('platform', {}).get('system', '').lower() == 'linux'
        context["is_windows"] = lambda: system_context.get('platform', {}).get('system', '').lower() == 'windows'
        context["is_macos"] = lambda: system_context.get('platform', {}).get('system', '').lower() == 'darwin'
        
        # Add package manager info
        if 'package_managers' in system_context:
            context["package_managers"] = system_context['package_managers']
        
        return context
    
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