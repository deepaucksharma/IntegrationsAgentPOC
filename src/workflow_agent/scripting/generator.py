"""Script generation for workflow agent."""
import logging
import re
from typing import Dict, Any, Optional

from ..core.state import WorkflowState
from ..config.templates import render_template
from ..utils.system import get_system_context
from ..integrations.registry import IntegrationRegistry

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """Generates scripts from templates."""
    
    def __init__(self, history_manager=None):
        self.history_manager = history_manager
        
    async def generate_script(
        self,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not state.target_name or not state.action:
            return {"error": "Missing target_name or action"}
        
        # Normalize integration type by removing underscores and lowercasing
        integration_key = state.integration_type.replace("_", "").lower() if state.integration_type else None
        if integration_key:
            integration_handler = IntegrationRegistry.get_integration(integration_key)
            if integration_handler:
                try:
                    handler = integration_handler()
                    result = await handler.handle(state, config)
                    if "script" in result:
                        return result
                except Exception as e:
                    logger.error(f"Integration handler error: {e}")
        
        template_key = f"{state.target_name}-{state.action}"
        script = render_template(template_key, {
            "target_name": state.target_name,
            "action": state.action,
            "parameters": state.parameters,
            "system_context": state.system_context or get_system_context()
        })
        
        if not script:
            return {"error": f"No template found for {template_key} and no integration handler provided a script"}
        
        if config and config.get("rule_based_optimization", False):
            script = self._apply_optimization(script, state)
        
        return {
            "script": script,
            "template_key": template_key
        }
    
    def _apply_optimization(self, script: str, state: WorkflowState) -> str:
        # Ensure error handling settings are enhanced
        if "set -e" in script and "set -o pipefail" not in script:
            script = script.replace("set -e", "set -e\nset -o pipefail")
        # Inject a logging function with properly escaped quotes
        if "log_message" not in script:
            script = re.sub(
                r'(#!/usr/bin/env bash\n)',
                r'\1\n# Add logging function\nlog_message() {\n    echo "[$(date \'+%Y-%m-%d %H:%M:%S\')] $1"\n}\n\n',
                script
            )
        # Make mkdir commands idempotent
        script = re.sub(
            r'mkdir\s+([^-])',
            r'mkdir -p \1',
            script
        )
        return script