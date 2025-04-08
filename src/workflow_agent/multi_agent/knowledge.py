"""
Enhanced KnowledgeAgent: Manages documentation and knowledge using LLM-driven understanding.
"""
import logging
import yaml
import json
import os
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import hashlib
import time

from ..core.message_bus import MessageBus
from ..core.state import WorkflowState
from ..storage.knowledge_base import KnowledgeBase
from ..llm.service import LLMService, LLMProvider

logger = logging.getLogger(__name__)

class KnowledgeAgent:
    """
    LLM-enhanced agent responsible for retrieving, analyzing, and understanding integration documentation.
    """
    
    def __init__(
        self, 
        message_bus: MessageBus, 
        knowledge_base: Optional[KnowledgeBase] = None,
        llm_service: Optional[LLMService] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.message_bus = message_bus
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.llm_service = llm_service or LLMService()
        self.config = config or {}
        
        # Additional paths for documentation
        self.documentation_paths = [
            Path(self.config.get("documentation_dir", "knowledge")),
            Path("doc"),
            Path("documentation"),
            Path("docs"),
        ]
        
        # Cache for parsed documentation
        self.parsed_docs_cache = {}
    
    async def initialize(self) -> None:
        """Initialize the knowledge agent with enhanced document understanding."""
        # Subscribe to message bus topics
        logger.info("Initializing KnowledgeAgent with LLM-driven document understanding...")
        await self.message_bus.subscribe("retrieve_knowledge", self._handle_retrieve_knowledge)
        await self.message_bus.subscribe("query_knowledge", self._handle_query_knowledge)
        await self.message_bus.subscribe("analyze_documentation", self._handle_analyze_documentation)
        await self.message_bus.subscribe("extract_parameters", self._handle_extract_parameters)
        
        # Initialize knowledge base
        await self.knowledge_base.initialize()
        
        # Index documentation from all sources
        indexed_count = await self._index_all_documentation()
        logger.info(f"Indexed {indexed_count} documentation files")
        
        logger.info("KnowledgeAgent initialization complete")
    
    async def _index_all_documentation(self) -> int:
        """Index documentation from all possible sources."""
        indexed_count = 0
        
        # Start with built-in documentation
        indexed_count += await self._index_built_in_documentation()
        
        # Try to index documentation from additional paths
        for doc_path in self.documentation_paths:
            if doc_path.exists():
                logger.info(f"Indexing documentation from {doc_path}")
                indexed_count += await self._index_documentation_path(doc_path)
        
        # Search for documentation in New Relic URLs
        indexed_count += await self._index_external_documentation()
        
        return indexed_count
    
    async def _index_built_in_documentation(self) -> int:
        """Index all YAML files in the built-in integrations directory."""
        docs_path = Path(__file__).parent.parent / "integrations"
        if not docs_path.exists():
            logger.info(f"Built-in documentation path not found: {docs_path}")
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
                logger.warning("No built-in documentation path found")
                return 0
        
        return await self._index_documentation_path(docs_path)
    
    async def _index_documentation_path(self, path: Path) -> int:
        """Index documentation files from a specific path."""
        indexed_count = 0
        
        # Index YAML files
        for yaml_file in path.glob("**/*.yaml"):
            try:
                with open(yaml_file, "r") as f:
                    content = yaml.safe_load(f)
                
                if not content:
                    continue
                    
                # Try to determine integration type and name from path
                rel_path = yaml_file.relative_to(path) if path in yaml_file.parents else yaml_file
                parts = list(rel_path.parts)
                
                if len(parts) >= 2:
                    integration_type = parts[0]
                    target_name = parts[1]
                    doc_type = yaml_file.stem
                else:
                    # Use filename as integration type
                    integration_type = yaml_file.stem
                    target_name = integration_type
                    doc_type = "definition"
                
                await self.knowledge_base.add_document(
                    integration_type=integration_type,
                    target_name=target_name,
                    doc_type=doc_type,
                    content=content
                )
                indexed_count += 1
                logger.debug(f"Indexed YAML document: {yaml_file}")
            except Exception as e:
                logger.warning(f"Error indexing YAML document {yaml_file}: {e}")
        
        # Index Markdown files
        for md_file in path.glob("**/*.md"):
            try:
                with open(md_file, "r") as f:
                    content = f.read()
                
                if not content:
                    continue
                
                # Try to determine integration type and name from path
                rel_path = md_file.relative_to(path) if path in md_file.parents else md_file
                parts = list(rel_path.parts)
                
                if len(parts) >= 2:
                    integration_type = parts[0]
                    target_name = parts[1]
                    doc_type = "documentation"
                else:
                    # Use filename as integration type
                    integration_type = md_file.stem
                    target_name = integration_type
                    doc_type = "documentation"
                
                # Use LLM to analyze the markdown documentation
                analyzed_content = await self._analyze_markdown_document(content, integration_type)
                
                await self.knowledge_base.add_document(
                    integration_type=integration_type,
                    target_name=target_name,
                    doc_type=doc_type,
                    content=analyzed_content
                )
                indexed_count += 1
                logger.debug(f"Indexed and analyzed Markdown document: {md_file}")
            except Exception as e:
                logger.warning(f"Error indexing Markdown document {md_file}: {e}")
        
        # Index text files
        for txt_file in path.glob("**/*.txt"):
            try:
                with open(txt_file, "r") as f:
                    content = f.read()
                
                if not content:
                    continue
                
                # Try to determine integration type and name from path
                rel_path = txt_file.relative_to(path) if path in txt_file.parents else txt_file
                parts = list(rel_path.parts)
                
                if len(parts) >= 2:
                    integration_type = parts[0]
                    target_name = parts[1]
                    doc_type = "documentation"
                else:
                    # Use filename as integration type
                    integration_type = txt_file.stem
                    target_name = integration_type
                    doc_type = "documentation"
                
                # Use LLM to analyze the text documentation
                analyzed_content = await self._analyze_text_document(content, integration_type)
                
                await self.knowledge_base.add_document(
                    integration_type=integration_type,
                    target_name=target_name,
                    doc_type=doc_type,
                    content=analyzed_content
                )
                indexed_count += 1
                logger.debug(f"Indexed and analyzed text document: {txt_file}")
            except Exception as e:
                logger.warning(f"Error indexing text document {txt_file}: {e}")
        
        return indexed_count
    
    async def _index_external_documentation(self) -> int:
        """Index documentation from external sources like New Relic's website."""
        # Not implemented yet - would require web scraping capabilities
        logger.info("External documentation indexing not implemented yet")
        return 0
    
    async def _analyze_markdown_document(self, content: str, integration_type: str) -> Dict[str, Any]:
        """
        Use LLM to analyze a markdown document and extract structured information.
        
        Args:
            content: Markdown document content
            integration_type: Integration type
            
        Returns:
            Structured information extracted from the document
        """
        # Check if we have a cached analysis
        cache_key = f"md_analysis_{hashlib.md5(content.encode()).hexdigest()}"
        if cache_key in self.parsed_docs_cache:
            return self.parsed_docs_cache[cache_key]
        
        prompt = f"""
        Analyze this New Relic integration documentation for {integration_type} and extract structured information.
        
        DOCUMENTATION:
        ```markdown
        {content[:10000]}  # Limit to 10k characters for token reasons
        ```
        
        Extract the following information:
        1. Integration name/type
        2. Description
        3. Parameters (name, description, type, required, default value)
        4. Installation steps
        5. Configuration steps
        6. Verification steps
        7. Uninstallation steps
        8. Troubleshooting tips
        9. System requirements and prerequisites
        
        Return the extracted information as a JSON object with these keys:
        - name: The name/type of the integration
        - description: A description of the integration
        - parameters: Array of parameter objects
        - installation: Array of installation steps
        - configuration: Array of configuration steps
        - verification: Array of verification steps
        - uninstallation: Array of uninstallation steps or null if not specified
        - troubleshooting: Array of troubleshooting tips or null if not specified
        - requirements: Object describing system requirements or null if not specified
        
        For each parameter, include:
        - name: Parameter name
        - description: Parameter description
        - type: Parameter type (string, integer, boolean, etc.)
        - required: Boolean indicating if the parameter is required
        - default: Default value or null if none
        """
        
        try:
            json_response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert at analyzing technical documentation and extracting structured information.",
                temperature=0.1  # Low temperature for more deterministic results
            )
            
            # Cache the analysis
            self.parsed_docs_cache[cache_key] = json_response
            
            return json_response
        except Exception as e:
            logger.warning(f"Error analyzing markdown document: {e}")
            # Return basic structure if analysis fails
            return {
                "name": integration_type,
                "description": "Documentation analysis failed",
                "parameters": [],
                "installation": [],
                "configuration": [],
                "verification": [],
                "uninstallation": [],
                "troubleshooting": [],
                "requirements": None
            }
    
    async def _analyze_text_document(self, content: str, integration_type: str) -> Dict[str, Any]:
        """Analyze a text document using LLM."""
        # Similar to markdown analysis but for plain text
        return await self._analyze_markdown_document(content, integration_type)
    
    async def _handle_retrieve_knowledge(self, message: Dict[str, Any]) -> None:
        """
        Handle knowledge retrieval request with LLM-enhanced understanding.
        
        When the coordinator requests knowledge, this method:
        1. Retrieves basic documentation from the knowledge base
        2. Uses LLM to enhance understanding of the documentation
        3. Generates additional context based on the integration type
        4. Updates the workflow state with the enhanced knowledge
        """
        workflow_id = message["workflow_id"]
        state_dict = message["state"]
        config = message.get("config", {})
        
        try:
            state = WorkflowState(**state_dict)
            logger.info(f"[KnowledgeAgent] Retrieving knowledge for {state.integration_type}/{state.target_name}")
            
            # 1. Retrieve base documentation from knowledge base
            docs = await self.knowledge_base.retrieve_documents(
                integration_type=state.integration_type,
                target_name=state.target_name,
                action=state.action
            )
            
            # 2. Check if we need to generate documentation with LLM
            if not docs or not docs.get("definition"):
                logger.info(f"No documentation found for {state.integration_type}/{state.target_name}. Generating with LLM.")
                llm_docs = await self._generate_documentation_with_llm(state)
                docs = {**docs, **llm_docs} if docs else llm_docs
            
            # 3. Enhance documentation with LLM analysis
            enhanced_docs = await self._enhance_documentation_with_llm(docs, state)
            
            # 4. Update state with enhanced documentation
            state.template_data = enhanced_docs.get("definition", {})
            state.parameter_schema = enhanced_docs.get("parameters", {})
            state.verification_data = enhanced_docs.get("verification", {})
            
            # 5. Add reasoning about knowledge for the coordinator
            knowledge_reasoning = await self._generate_knowledge_reasoning(state, enhanced_docs)
            state.knowledge_reasoning = knowledge_reasoning
            
            # 6. Identify template path (but LLM will generate if needed)
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
                logger.info(f"No template found for {template_rel}, LLM will generate script from scratch")
                # No default fallback - LLM will generate script from scratch
            
            logger.info(f"[KnowledgeAgent] Knowledge retrieval and enhancement complete for {state.integration_type}/{state.target_name}")
            
            # Publish the updated state
            await self.message_bus.publish("knowledge_retrieved", {
                "workflow_id": workflow_id,
                "state": state.model_dump(),
                "knowledge_found": bool(docs),
                "template_found": template_found
            })
            
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {str(e)}", exc_info=True)
            await self.message_bus.publish("error", {
                "workflow_id": workflow_id,
                "error": f"Error retrieving knowledge: {str(e)}"
            })
    
    async def _generate_documentation_with_llm(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Generate documentation for an integration using LLM when no docs exist.
        
        Args:
            state: Workflow state
            
        Returns:
            Generated documentation
        """
        logger.info(f"Generating documentation for {state.integration_type} with LLM")
        
        prompt = f"""
        Generate comprehensive documentation for a New Relic {state.integration_type} integration.
        
        Consider these details:
        - Integration type: {state.integration_type}
        - Target name: {state.target_name}
        - Action requested: {state.action}
        - Parameters provided: {json.dumps(state.parameters, indent=2)}
        
        Create complete documentation covering:
        1. Integration description and purpose
        2. Required parameters (with defaults if applicable)
        3. Optional parameters (with defaults if applicable)
        4. Installation procedure
        5. Configuration steps
        6. Verification methods
        7. Uninstallation procedure
        8. Common troubleshooting steps
        
        Format your response as a JSON object with the following structure:
        {{
            "definition": {{
                "name": "string",
                "description": "string",
                "version": "string",
                "parameters": [
                    {{
                        "name": "string",
                        "description": "string",
                        "required": boolean,
                        "type": "string",
                        "default": "any" or null
                    }}
                ],
                "installation": [
                    {{
                        "step": "string",
                        "description": "string",
                        "command": "string" or null
                    }}
                ],
                "configuration": [
                    {{
                        "step": "string", 
                        "description": "string",
                        "file_path": "string" or null,
                        "content": "string" or null
                    }}
                ],
                "verification": [
                    {{
                        "step": "string",
                        "description": "string",
                        "command": "string" or null,
                        "expected_output": "string" or null
                    }}
                ],
                "uninstallation": [
                    {{
                        "step": "string",
                        "description": "string",
                        "command": "string" or null
                    }}
                ]
            }}
        }}
        """
        
        try:
            json_response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in New Relic integration documentation. Generate accurate and detailed documentation.",
                temperature=0.2
            )
            
            # Validate the response has the right structure
            if not isinstance(json_response, dict) or "definition" not in json_response:
                logger.warning("LLM did not generate documentation in the expected format")
                # Create a minimal valid structure
                json_response = {
                    "definition": {
                        "name": state.integration_type,
                        "description": f"{state.integration_type} integration for New Relic",
                        "version": "1.0.0",
                        "parameters": [],
                        "installation": [],
                        "configuration": [],
                        "verification": [],
                        "uninstallation": []
                    }
                }
            
            return json_response
            
        except Exception as e:
            logger.error(f"Error generating documentation with LLM: {e}")
            # Return a minimal document structure
            return {
                "definition": {
                    "name": state.integration_type,
                    "description": f"{state.integration_type} integration for New Relic",
                    "version": "1.0.0",
                    "parameters": []
                }
            }
    
    async def _enhance_documentation_with_llm(self, docs: Dict[str, Any], state: WorkflowState) -> Dict[str, Any]:
        """
        Enhance existing documentation with LLM analysis.
        
        Args:
            docs: Existing documentation
            state: Workflow state
            
        Returns:
            Enhanced documentation
        """
        logger.info(f"Enhancing documentation for {state.integration_type} with LLM")
        
        definition = docs.get("definition", {})
        
        # Skip enhancement if no definition or if it's already been enhanced
        if not definition or definition.get("enhanced", False):
            return docs
        
        # Extract information from definition
        action = state.action.lower()
        relevant_sections = []
        
        if action == "install":
            relevant_sections = ["installation", "configuration"]
        elif action == "verify":
            relevant_sections = ["verification"]
        elif action in ["remove", "uninstall"]:
            relevant_sections = ["uninstallation"]
        
        # Check if documentation is missing important sections
        missing_sections = [section for section in relevant_sections if section not in definition or not definition.get(section)]
        
        if not missing_sections:
            # No missing sections, mark as enhanced and return
            definition["enhanced"] = True
            docs["definition"] = definition
            return docs
        
        # Generate missing sections with LLM
        prompt = f"""
        Enhance the existing documentation for a New Relic {state.integration_type} integration.
        
        Existing documentation:
        {json.dumps(definition, indent=2)}
        
        The documentation is missing these sections: {', '.join(missing_sections)}
        
        Generate comprehensive content for the missing sections based on your knowledge of New Relic integrations.
        
        Action being performed: {state.action}
        Target system type: {"Windows" if state.system_context.get("is_windows", False) else "Linux/Unix"}
        Parameters available: {json.dumps(state.parameters, indent=2)}
        
        Format your response as a JSON object containing only the missing sections with the same structure as the existing documentation.
        """
        
        try:
            json_response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in New Relic integration documentation. Generate accurate and detailed content for missing documentation sections.",
                temperature=0.2
            )
            
            # Merge the generated sections into the existing documentation
            for section in missing_sections:
                if section in json_response:
                    definition[section] = json_response[section]
            
            # Mark as enhanced
            definition["enhanced"] = True
            docs["definition"] = definition
            
            return docs
            
        except Exception as e:
            logger.warning(f"Error enhancing documentation with LLM: {e}")
            return docs
    
    async def _generate_knowledge_reasoning(self, state: WorkflowState, docs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate reasoning about the knowledge for the coordinator.
        
        Args:
            state: Workflow state
            docs: Documentation
            
        Returns:
            Reasoning about the knowledge
        """
        definition = docs.get("definition", {})
        
        prompt = f"""
        Analyze the available knowledge for the New Relic {state.integration_type} integration and provide reasoning.
        
        Integration details:
        - Type: {state.integration_type}
        - Action: {state.action}
        - Target system: {"Windows" if state.system_context.get("is_windows", False) else "Linux/Unix"}
        
        Available documentation:
        {json.dumps(definition, indent=2)}
        
        Provided parameters:
        {json.dumps(state.parameters, indent=2)}
        
        Evaluate and explain:
        1. Is the documentation sufficient for the requested action?
        2. Are there any missing parameters that will be needed?
        3. Are there any potential challenges or issues to be aware of?
        4. What verification steps are most important for this integration?
        5. What approach would you recommend for this integration?
        
        Include any other relevant observations or recommendations.
        Format your response as a JSON object.
        """
        
        try:
            json_response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in analyzing integration requirements and knowledge.",
                temperature=0.2
            )
            
            return json_response
            
        except Exception as e:
            logger.warning(f"Error generating knowledge reasoning: {e}")
            return {
                "documentation_sufficient": bool(definition),
                "missing_parameters": [],
                "potential_challenges": [],
                "important_verification": [],
                "recommended_approach": f"Proceed with {state.action} using available documentation"
            }
    
    async def _handle_query_knowledge(self, message: Dict[str, Any]) -> None:
        """
        Handle dynamic knowledge queries from other agents.
        
        This allows other agents to ask specific questions about the integration.
        """
        workflow_id = message.get("workflow_id")
        query = message.get("query")
        context = message.get("context", {})
        
        if not query:
            await self.message_bus.publish("query_response", {
                "workflow_id": workflow_id,
                "error": "No query provided",
                "result": None
            })
            return
        
        try:
            # Get integration context
            integration_type = context.get("integration_type")
            target_name = context.get("target_name")
            
            # Retrieve base documentation
            docs = {}
            if integration_type:
                docs = await self.knowledge_base.retrieve_documents(
                    integration_type=integration_type,
                    target_name=target_name or integration_type,
                    action=context.get("action", "all")
                )
            
            # Parse query using LLM
            query_result = await self._process_knowledge_query(query, docs, context)
            
            # Send response
            await self.message_bus.publish("query_response", {
                "workflow_id": workflow_id,
                "result": query_result
            })
            
        except Exception as e:
            logger.error(f"Error processing knowledge query: {e}")
            await self.message_bus.publish("query_response", {
                "workflow_id": workflow_id,
                "error": f"Error processing query: {str(e)}",
                "result": None
            })
    
    async def _process_knowledge_query(self, query: str, docs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a knowledge query using LLM.
        
        Args:
            query: The question to answer
            docs: Available documentation
            context: Query context
            
        Returns:
            Query response
        """
        # Format available documentation
        doc_content = json.dumps(docs, indent=2) if docs else "No documentation available"
        
        prompt = f"""
        Answer the following question about a New Relic integration based on the available documentation:
        
        Question: {query}
        
        Context:
        {json.dumps(context, indent=2)}
        
        Available documentation:
        {doc_content}
        
        If the documentation doesn't contain the answer, use your knowledge to provide the best possible answer
        and indicate that it's based on general knowledge rather than specific documentation.
        
        Format your answer as a JSON object with these fields:
        - answer: Your complete answer to the question
        - confidence: High, Medium, or Low indicating your confidence
        - source: "documentation" or "general_knowledge"
        - references: Any specific sections of the documentation you referenced (if applicable)
        """
        
        try:
            json_response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in New Relic integrations providing accurate answers to technical questions.",
                temperature=0.2
            )
            
            return json_response
            
        except Exception as e:
            logger.warning(f"Error processing knowledge query: {e}")
            return {
                "answer": f"Unable to process query: {query}",
                "confidence": "Low",
                "source": "error",
                "error": str(e)
            }
    
    async def _handle_analyze_documentation(self, message: Dict[str, Any]) -> None:
        """
        Handle requests to analyze integration documentation.
        
        This allows other agents to request in-depth analysis of documentation.
        """
        workflow_id = message.get("workflow_id")
        integration_type = message.get("integration_type")
        doc_content = message.get("content")
        
        if not integration_type or not doc_content:
            await self.message_bus.publish("documentation_analysis", {
                "workflow_id": workflow_id,
                "error": "Missing integration_type or content",
                "result": None
            })
            return
        
        try:
            # Use LLM to analyze the documentation
            if isinstance(doc_content, str):
                # Text content
                analysis = await self._analyze_text_document(doc_content, integration_type)
            elif isinstance(doc_content, dict):
                # Already structured content, enhance it
                analysis = await self._enhance_documentation_with_llm({"definition": doc_content}, WorkflowState(
                    action="analyze",
                    target_name=integration_type,
                    integration_type=integration_type
                ))
                analysis = analysis.get("definition", {})
            else:
                analysis = {"error": "Unsupported content type"}
            
            # Send response
            await self.message_bus.publish("documentation_analysis", {
                "workflow_id": workflow_id,
                "result": analysis
            })
            
        except Exception as e:
            logger.error(f"Error analyzing documentation: {e}")
            await self.message_bus.publish("documentation_analysis", {
                "workflow_id": workflow_id,
                "error": f"Error analyzing documentation: {str(e)}",
                "result": None
            })
    
    async def _handle_extract_parameters(self, message: Dict[str, Any]) -> None:
        """
        Handle requests to extract and validate parameters for an integration.
        
        This allows other agents to request parameter validation and extraction.
        """
        workflow_id = message.get("workflow_id")
        integration_type = message.get("integration_type")
        provided_params = message.get("parameters", {})
        
        if not integration_type:
            await self.message_bus.publish("parameter_extraction", {
                "workflow_id": workflow_id,
                "error": "Missing integration_type",
                "result": None
            })
            return
        
        try:
            # Retrieve documentation
            docs = await self.knowledge_base.retrieve_documents(
                integration_type=integration_type,
                target_name=integration_type,
                action="all"
            )
            
            # Extract parameter definitions
            param_definitions = []
            if docs and "definition" in docs and "parameters" in docs["definition"]:
                param_definitions = docs["definition"]["parameters"]
            
            # Use LLM to analyze parameters
            params_result = await self._analyze_parameters(integration_type, param_definitions, provided_params)
            
            # Send response
            await self.message_bus.publish("parameter_extraction", {
                "workflow_id": workflow_id,
                "result": params_result
            })
            
        except Exception as e:
            logger.error(f"Error extracting parameters: {e}")
            await self.message_bus.publish("parameter_extraction", {
                "workflow_id": workflow_id,
                "error": f"Error extracting parameters: {str(e)}",
                "result": None
            })
    
    async def _analyze_parameters(
        self, 
        integration_type: str, 
        param_definitions: List[Dict[str, Any]], 
        provided_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze parameters using LLM.
        
        Args:
            integration_type: Integration type
            param_definitions: Parameter definitions from documentation
            provided_params: Parameters provided by the user
            
        Returns:
            Parameter analysis
        """
        prompt = f"""
        Analyze and validate parameters for a New Relic {integration_type} integration.
        
        Parameter definitions from documentation:
        {json.dumps(param_definitions, indent=2)}
        
        Parameters provided:
        {json.dumps(provided_params, indent=2)}
        
        Please:
        1. Determine if all required parameters are provided
        2. Validate parameter types and values
        3. Fill in missing optional parameters with defaults
        4. Identify any parameters provided that aren't in the documentation
        
        Format your response as a JSON object with:
        - validated: Boolean indicating if validation passed
        - missing_required: Array of missing required parameters
        - invalid_parameters: Array of invalid parameters with reasons
        - complete_parameters: Object with all parameters including defaults
        - undefined_parameters: Array of parameters not in documentation
        """
        
        try:
            json_response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert in validating integration parameters against documentation requirements.",
                temperature=0.1
            )
            
            return json_response
            
        except Exception as e:
            logger.warning(f"Error analyzing parameters: {e}")
            return {
                "validated": len(param_definitions) == 0,  # If no definitions, consider valid
                "missing_required": [],
                "invalid_parameters": [],
                "complete_parameters": provided_params,
                "undefined_parameters": [] if not param_definitions else list(provided_params.keys())
            }
