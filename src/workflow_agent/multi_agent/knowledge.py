"""
KnowledgeAgent: Manages documentation and knowledge retrieval for integrations.
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio

from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..storage.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

class KnowledgeAgent:
    """
    Responsible for retrieving and managing integration documentation.
    """
    
    def __init__(self, message_bus: MessageBus, knowledge_base: Optional[KnowledgeBase] = None):
        self.message_bus = message_bus
        self.knowledge_base = knowledge_base or KnowledgeBase()
    
    async def initialize(self) -> None:
        """Initialize the knowledge agent."""
        await self.message_bus.subscribe("retrieve_knowledge", self._handle_retrieve_knowledge)
        await self.message_bus.subscribe("query_knowledge", self._handle_query_knowledge)
        await self.knowledge_base.initialize()
        await self._index_default_documentation()
    
    async def _index_default_documentation(self) -> None:
        """Index all YAML files in the integrations directory."""
        docs_path = Path(__file__).parent.parent / "integrations"
        if not docs_path.exists():
            logger.warning(f"Default documentation path not found: {docs_path}")
            # Try alternate paths
            alt_paths = [
                Path.cwd() / "src" / "workflow_agent" / "integrations",
                Path(__file__).resolve().parent.parent.parent.parent / "src" / "workflow_agent" / "integrations"
            ]
            for path in alt_paths:
                if path.exists():
                    docs_path = path
                    logger.info(f"Found alternate documentation path: {docs_path}")
                    break
            else:
                logger.warning("No documentation path found, skipping indexing")
                return
        
        indexed_count = 0
        for yaml_file in docs_path.glob("**/*.yaml"):
            try:
                with open(yaml_file, "r") as f:
                    content = yaml.safe_load(f)
                if not content:
                    continue
                rel_path = yaml_file.relative_to(docs_path)
                parts = list(rel_path.parts)
                if len(parts) >= 2:
                    integration_type = parts[0]
                    target_name = parts[1]
                    doc_type = yaml_file.stem
                    await self.knowledge_base.add_document(
                        integration_type=integration_type,
                        target_name=target_name,
                        doc_type=doc_type,
                        content=content
                    )
                    indexed_count += 1
            except Exception as e:
                logger.error(f"Error indexing document {yaml_file}: {e}")
        
        logger.info(f"Indexed {indexed_count} documentation files")
    
    async def _handle_retrieve_knowledge(self, message: Dict[str, Any]) -> None:
        """Handle knowledge retrieval request."""
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        try:
            state = WorkflowState(**state_dict)
            docs = await self.knowledge_base.retrieve_documents(
                integration_type=state.integration_type,
                target_name=state.target_name,
                action=state.action
            )
            state.template_data = docs.get("definition", {})
            state.parameter_schema = docs.get("parameters", {})
            state.verification_data = docs.get("verification", {})
            
            action_map = {
                "install": "install/base.sh.j2",
                "remove": "remove/base.sh.j2",
                "verify": "verify/base.sh.j2"
            }
            template_rel = action_map.get(state.action, "install/base.sh.j2")
            
            # Try different paths to find the template
            template_paths = [
                Path(__file__).parent.parent / "integrations" / "common_templates" / template_rel,
                Path.cwd() / "src" / "workflow_agent" / "integrations" / "common_templates" / template_rel,
                Path(__file__).resolve().parent.parent.parent.parent / "src" / "workflow_agent" / "integrations" / "common_templates" / template_rel
            ]
            
            template_found = False
            for template_path in template_paths:
                if template_path.exists():
                    state.template_path = str(template_path)
                    template_found = True
                    break
            
            if not template_found:
                logger.warning(f"No template found for {template_rel}, using default template")
                # Create a basic template as fallback
                if state.action == "install":
                    state.script = f"""#!/usr/bin/env bash
set -e
echo "Installing {{ target_name }}"
echo "Install complete."
"""
                elif state.action == "remove":
                    state.script = f"""#!/usr/bin/env bash
set -e
echo "Removing {{ target_name }}"
echo "Removal complete."
"""
                elif state.action == "verify":
                    state.script = f"""#!/usr/bin/env bash
set -e
echo "Verifying {{ target_name }}"
echo "Verification complete."
"""
            
            logger.info(f"[KnowledgeAgent] Retrieved documentation for {state.integration_type}/{state.target_name}")
            await self.message_bus.publish("knowledge_retrieved", {
                "workflow_id": workflow_id,
                "state": state.dict()
            })
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {e}")
            await self.message_bus.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error retrieving knowledge: {str(e)}"
            })
    
    async def _handle_query_knowledge(self, message: Dict[str, Any]) -> None:
        """Handle knowledge query request."""
        workflow_id = message.get("workflow_id")
        query = message.get("query")
        context = message.get("context", {})
        if not query:
            await self.message_bus.publish("query_response", {
                "workflow_id": workflow_id,
                "error": "No query provided"
            })
            return
        try:
            result = await self.knowledge_base.query(query, context)
            await self.message_bus.publish("query_response", {
                "workflow_id": workflow_id,
                "result": result
            })
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            await self.message_bus.publish("query_response", {
                "workflow_id": workflow_id,
                "error": f"Error processing query: {str(e)}"
            })