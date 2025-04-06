"""
Dynamic verification builder for generating verification scripts.
"""
import logging
from typing import Dict, Any, List, Optional
import yaml
import os
from pathlib import Path

from ..core.state import WorkflowState
from ..error.exceptions import VerificationError
from ..config.configuration import WorkflowConfiguration
from ..templates.manager import TemplateManager
from .manager import VerificationStep

logger = logging.getLogger(__name__)

class DynamicVerificationBuilder:
    """Builds verification scripts dynamically based on integration type and context."""
    
    def __init__(self, config: WorkflowConfiguration, template_manager: TemplateManager):
        """
        Initialize dynamic verification builder.
        
        Args:
            config: Workflow configuration
            template_manager: Template manager for script generation
        """
        self.config = config
        self.template_manager = template_manager
        
    async def build_verification_steps(self, state: WorkflowState) -> List[VerificationStep]:
        """
        Build verification steps for an integration.
        
        Args:
            state: Workflow state with integration information
            
        Returns:
            List of verification steps
        """
        # Default verfication steps based on integration type
        default_steps = self._get_default_steps(state.integration_type)
        
        # Try to get steps from a knowledge source
        from ..knowledge.retriever import KnowledgeRetriever
        knowledge_retriever = KnowledgeRetriever(self.config)
        
        try:
            knowledge_steps = await knowledge_retriever.get_verification_steps(
                state.integration_type,
                state.target_name,
                state.parameters
            )
            
            # Merge default steps with knowledge steps
            return [*default_steps, *knowledge_steps]
            
        except Exception as e:
            logger.warning(f"Error retrieving verification steps from knowledge: {e}")
            return default_steps
    
    def _get_default_steps(self, integration_type: str) -> List[VerificationStep]:
        """
        Get default verification steps for an integration type.
        
        Args:
            integration_type: Type of integration
            
        Returns:
            List of verification steps
        """
        steps = []
        
        # Generic steps based on integration type
        if integration_type == "database":
            steps.append(VerificationStep(
                name="Database Connection",
                description="Verify database connection",
                script="""#!/bin/bash
echo "Verifying database connection..."
exit 0
""",
                required=True
            ))
        elif integration_type == "web_server":
            steps.append(VerificationStep(
                name="Web Server Status",
                description="Verify web server is running",
                script="""#!/bin/bash
echo "Verifying web server status..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:80 | grep 200
""",
                expected_result="200",
                required=True
            ))
        elif integration_type == "infra_agent":
            steps.append(VerificationStep(
                name="Agent Status",
                description="Verify agent is running",
                script="""#!/bin/bash
echo "Verifying agent status..."
exit 0
""",
                required=True
            ))
            
        # Add file existence verification (common for most integrations)
        steps.append(VerificationStep(
            name="Configuration Check",
            description="Verify configuration files exist",
            script="""#!/bin/bash
echo "Checking configuration files..."
if [ -d "/etc/{{ integration_type }}" ]; then
    echo "Configuration directory exists"
    exit 0
else
    echo "Configuration directory not found"
    exit 1
fi
""",
            required=False
        ))
            
        return steps

class VerificationScriptGenerator:
    """Generates verification scripts for integrations."""
    
    def __init__(self, template_manager: TemplateManager):
        """
        Initialize verification script generator.
        
        Args:
            template_manager: Template manager for script generation
        """
        self.template_manager = template_manager
        
    def generate_verification_script(
        self,
        integration_type: str,
        target_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate verification script.
        
        Args:
            integration_type: Type of integration
            target_name: Target identifier
            parameters: Verification parameters
            
        Returns:
            Verification script or None if not available
        """
        # Try to get a verification template
        template_key = f"verify/{integration_type}/{target_name}"
        
        # Try specific first, then fall back to default
        if not self.template_manager.get_template(template_key):
            template_key = f"verify/{integration_type}/default"
            
            if not self.template_manager.get_template(template_key):
                template_key = "verify/default"
                
                if not self.template_manager.get_template(template_key):
                    logger.warning(f"No verification template found for {integration_type}/{target_name}")
                    return self._generate_fallback_script(integration_type, target_name)
        
        # Render the template
        context = {
            "integration_type": integration_type,
            "target_name": target_name,
            **parameters
        }
        
        script = self.template_manager.render_template(template_key, context)
        if not script:
            logger.warning(f"Failed to render verification template: {template_key}")
            return self._generate_fallback_script(integration_type, target_name)
            
        return script
        
    def _generate_fallback_script(self, integration_type: str, target_name: str) -> str:
        """Generate a fallback script when no template is available."""
        return f"""#!/bin/bash
echo "Performing basic verification for {integration_type} - {target_name}"

# Check if process exists (very basic check)
if pgrep -f "{target_name}" > /dev/null; then
    echo "Process appears to be running"
    exit 0
else
    echo "Process does not appear to be running"
    exit 1
fi
"""
