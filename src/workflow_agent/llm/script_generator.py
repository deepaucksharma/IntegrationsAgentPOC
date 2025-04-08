"""
Enhanced LLM-based script generation with adaptive learning and platform awareness.
"""
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import logging
import os
import json
import asyncio
import re
import time
from datetime import datetime
import hashlib

from ..core.state import WorkflowState, Change
from ..error.exceptions import ScriptError
from .service import LLMService, LLMProvider, LLMResponseFormat

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """
    Advanced script generator using LLM with platform awareness and adaptive learning.
    """

    def __init__(
        self, 
        llm_service: Optional[LLMService] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the LLM-based script generator with enhanced capabilities.
        
        Args:
            llm_service: LLM service for script generation
            config: Configuration options
        """
        self.config = config or {}
        self.llm_service = llm_service or LLMService(self.config.get("llm", {}))
        
        # Directory for generated scripts with metadata
        self.script_dir = Path(self.config.get("script_dir", "generated_scripts"))
        self.script_dir.mkdir(exist_ok=True)
        
        # Cache for generated scripts
        self.script_cache = {}
        
        # Store for successful templates and patterns
        self.learning_store = {}
        
        # Performance metrics for continuous improvement
        self.execution_metrics = {}
        
        logger.info("Enhanced LLM script generator initialized")

    async def generate_script(self, state: WorkflowState) -> WorkflowState:
        """
        Generate a script for a workflow state using LLM with enhanced context and capabilities.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with generated script
        """
        logger.info(f"Generating script for {state.integration_type}/{state.target_name} ({state.action})")
        
        try:
            # 1. Create detailed generation context
            context = await self._create_generation_context(state)
            
            # 2. Check for cached script or similar situations
            cache_key = self._get_cache_key(state)
            cached_result = await self._check_script_cache(cache_key, state)
            
            if cached_result and not self.config.get("skip_cache", False):
                logger.info(f"Using cached script for {cache_key}")
                script_content = cached_result["script"]
                
                # Update state with script
                updated_state = state.set_script(script_content)
                updated_state = updated_state.add_message("Using cached script from similar execution")
                
                # Document reasoning behind decision
                reasoning = {
                    "decision": "use_cached_script",
                    "reason": "Found cached script for similar execution",
                    "similarity_factors": cached_result.get("similarity_factors", []),
                    "cache_key": cache_key
                }
                
                updated_state = self._add_generation_metadata(updated_state, reasoning)
                return updated_state
            
            # 3. Determine platform and select appropriate template style
            is_windows = state.system_context.get('is_windows', False) or 'win' in state.system_context.get('platform', {}).get('system', '').lower()
            script_language = "PowerShell" if is_windows else "Bash"
            
            # 4. Create detailed prompt with context awareness
            prompt = await self._create_generation_prompt(state, context, script_language)
            
            # 5. Generate script with LLM
            script_content = await self._generate_script_content(prompt, state, script_language)
            
            # Check for empty or invalid script
            if not script_content or len(script_content.strip()) < 10:
                raise ScriptError("Generated script is empty or too short")
                
            # 6. Post-process script with enhancements
            enhanced_script = await self._post_process_script(script_content, state, script_language)
            
            # 7. Save script to file with metadata
            script_path = await self._save_script_to_file(enhanced_script, state, script_language)
            
            # 8. Update cache
            self._update_script_cache(cache_key, {
                "script": enhanced_script,
                "path": str(script_path),
                "generated_at": datetime.now().isoformat(),
                "state_summary": {
                    "action": state.action,
                    "integration_type": state.integration_type,
                    "target_name": state.target_name,
                    "platform": state.system_context.get('platform', {})
                }
            })
            
            # 9. Update state with script and metadata
            updated_state = state.set_script(enhanced_script)
            updated_state = updated_state.add_message(f"Generated {script_language} script for {state.action}")
            
            # Document the generation reasoning
            reasoning = {
                "decision": "generate_new_script",
                "script_language": script_language,
                "platform_factors": context.get("platform_factors", []),
                "knowledge_factors": context.get("knowledge_factors", []),
                "script_path": str(script_path)
            }
            
            updated_state = self._add_generation_metadata(updated_state, reasoning)
            
            logger.info(f"Successfully generated script for {state.integration_type}/{state.target_name}")
            return updated_state
            
        except Exception as e:
            logger.error(f"Error generating script: {e}", exc_info=True)
            return state.set_error(f"Script generation error: {str(e)}")

    async def _create_generation_context(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Create detailed context for script generation with platform and integration info.
        
        Args:
            state: Current workflow state
            
        Returns:
            Detailed generation context
        """
        # Extract platform details
        platform_info = state.system_context.get('platform', {})
        is_windows = state.system_context.get('is_windows', False) or 'win' in platform_info.get('system', '').lower()
        
        # Determine platform-specific factors
        platform_factors = []
        
        if is_windows:
            platform_factors.append("windows_os")
            # Check Windows version
            version = platform_info.get('version', '')
            if '10' in version:
                platform_factors.append("windows_10")
            elif '11' in version:
                platform_factors.append("windows_11")
            elif 'server' in version.lower():
                platform_factors.append("windows_server")
        else:
            platform_factors.append("unix_like_os")
            
            # Check Linux distribution
            distro = platform_info.get('distribution', '').lower()
            if 'ubuntu' in distro:
                platform_factors.append("ubuntu_linux")
            elif 'debian' in distro:
                platform_factors.append("debian_linux")
            elif 'centos' in distro or 'rhel' in distro or 'fedora' in distro:
                platform_factors.append("rhel_family")
            elif 'alpine' in distro:
                platform_factors.append("alpine_linux")
        
        # Analyze available documentation and knowledge
        knowledge_factors = []
        
        definition = state.template_data.get('definition', {})
        if definition:
            knowledge_factors.append("documentation_available")
            
            # Check for specific installation steps
            if definition.get('installation'):
                knowledge_factors.append("installation_steps_available")
                
            # Check for specific configuration steps
            if definition.get('configuration'):
                knowledge_factors.append("configuration_steps_available")
                
            # Check for verification steps
            if definition.get('verification'):
                knowledge_factors.append("verification_steps_available")
                
            # Check for uninstallation steps
            if definition.get('uninstallation'):
                knowledge_factors.append("uninstallation_steps_available")
        
        # Check knowledge reasoning if available
        if hasattr(state, 'knowledge_reasoning') and state.knowledge_reasoning:
            knowledge_factors.append("knowledge_reasoning_available")
            
            reasoning = state.knowledge_reasoning
            if reasoning.get('documentation_sufficient') is False:
                knowledge_factors.append("documentation_insufficient")
                
            if reasoning.get('missing_parameters'):
                knowledge_factors.append("missing_parameters_identified")
                
            if reasoning.get('potential_challenges'):
                knowledge_factors.append("potential_challenges_identified")
        
        # Check parameter completeness
        if state.parameters:
            knowledge_factors.append("parameters_provided")
        
        # Construct context dictionary
        context = {
            "platform_info": platform_info,
            "is_windows": is_windows,
            "platform_factors": platform_factors,
            "knowledge_factors": knowledge_factors,
            "script_language": "PowerShell" if is_windows else "Bash",
            "integration_details": {
                "type": state.integration_type,
                "name": state.target_name,
                "action": state.action,
                "parameters": state.parameters
            },
            "documentation": definition,
            "knowledge_reasoning": getattr(state, 'knowledge_reasoning', {})
        }
        
        return context

    async def _check_script_cache(self, cache_key: str, state: WorkflowState) -> Optional[Dict[str, Any]]:
        """
        Check for cached scripts for similar situations.
        
        Args:
            cache_key: Cache key for this state
            state: Current workflow state
            
        Returns:
            Cached script entry if found, None otherwise
        """
        # Direct cache hit
        if cache_key in self.script_cache:
            return self.script_cache[cache_key]
        
        # Look for similar situations
        similarity_threshold = self.config.get("similarity_threshold", 0.8)
        
        for key, entry in self.script_cache.items():
            similarity_score = await self._calculate_similarity(state, entry.get("state_summary", {}))
            
            if similarity_score >= similarity_threshold:
                logger.info(f"Found similar script with similarity score {similarity_score}")
                # Add similarity info
                entry["similarity_factors"] = ["similar_integration", "similar_parameters", "same_action", "same_platform"]
                entry["similarity_score"] = similarity_score
                return entry
        
        return None

    async def _calculate_similarity(self, state: WorkflowState, cached_summary: Dict[str, Any]) -> float:
        """
        Calculate similarity between current state and cached summary.
        
        Args:
            state: Current workflow state
            cached_summary: Summary of cached state
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Basic matching factors
        score = 0.0
        
        # Same action is important (33%)
        if state.action == cached_summary.get("action"):
            score += 0.33
        
        # Same integration type is important (33%)
        if state.integration_type == cached_summary.get("integration_type"):
            score += 0.33
        
        # Platform similarity is important (33%)
        current_platform = state.system_context.get('platform', {})
        cached_platform = cached_summary.get('platform', {})
        
        platform_similarity = 0.0
        
        # Same OS family
        if (current_platform.get('system') == cached_platform.get('system')):
            platform_similarity += 0.2
        
        # Same distribution
        if (current_platform.get('distribution') == cached_platform.get('distribution')):
            platform_similarity += 0.1
        
        # Similar version
        if current_platform.get('version') and cached_platform.get('version'):
            if current_platform.get('version') == cached_platform.get('version'):
                platform_similarity += 0.03
        
        score += platform_similarity * 0.33
        
        return score

    async def _create_generation_prompt(
        self, 
        state: WorkflowState, 
        context: Dict[str, Any],
        script_language: str
    ) -> str:
        """
        Create detailed prompt for script generation with context awareness.
        
        Args:
            state: Current workflow state
            context: Generation context
            script_language: Script language (PowerShell or Bash)
            
        Returns:
            Detailed prompt for script generation
        """
        # Create platform-specific section
        platform_section = "Target System Details:\n"
        
        if context["is_windows"]:
            platform_section += f"""
- Operating System: Windows
- Version: {context['platform_info'].get('version', 'Unknown')}
- PowerShell version: {context['platform_info'].get('powershell_version', '5.1+')}\n
"""
        else:
            platform_section += f"""
- Operating System: {context['platform_info'].get('system', 'Linux/Unix')}
- Distribution: {context['platform_info'].get('distribution', 'Unknown')}
- Version: {context['platform_info'].get('version', 'Unknown')}\n
"""
        
        # Create parameters section
        params_section = "Parameters:\n"
        
        for key, value in state.parameters.items():
            params_section += f"- {key}: {value}\n"
        
        # Create documentation section
        docs_section = ""
        definition = context.get("documentation", {})
        
        if definition:
            docs_section = "Integration Documentation:\n"
            
            if 'description' in definition:
                docs_section += f"Description: {definition['description']}\n\n"
            
            # Include relevant steps based on the action
            if state.action == "install" and 'installation' in definition:
                docs_section += "Installation Steps:\n"
                for step in definition['installation']:
                    step_desc = step.get('description', '') 
                    step_cmd = step.get('command', '')
                    docs_section += f"- {step_desc}" + (f" : `{step_cmd}`" if step_cmd else "") + "\n"
                docs_section += "\n"
                
            if state.action == "install" and 'configuration' in definition:
                docs_section += "Configuration Steps:\n"
                for step in definition['configuration']:
                    step_desc = step.get('description', '')
                    file_path = step.get('file_path', '')
                    content = step.get('content', '')
                    docs_section += f"- {step_desc}" + (f" (File: {file_path})" if file_path else "") + "\n"
                    if content:
                        docs_section += f"  Content: {content}\n"
                docs_section += "\n"
                
            if state.action == "verify" and 'verification' in definition:
                docs_section += "Verification Steps:\n"
                for step in definition['verification']:
                    step_desc = step.get('description', '')
                    step_cmd = step.get('command', '')
                    expected = step.get('expected_output', '')
                    docs_section += f"- {step_desc}" + (f" : `{step_cmd}`" if step_cmd else "") + "\n"
                    if expected:
                        docs_section += f"  Expected Output: {expected}\n"
                docs_section += "\n"
                
            if state.action in ["remove", "uninstall"] and 'uninstallation' in definition:
                docs_section += "Uninstallation Steps:\n"
                for step in definition['uninstallation']:
                    step_desc = step.get('description', '')
                    step_cmd = step.get('command', '')
                    docs_section += f"- {step_desc}" + (f" : `{step_cmd}`" if step_cmd else "") + "\n"
                docs_section += "\n"
        
        # Create knowledge reasoning section
        reasoning_section = ""
        if "knowledge_reasoning" in context and context["knowledge_reasoning"]:
            reasoning = context["knowledge_reasoning"]
            reasoning_section = "Integration Insights:\n"
            
            if "missing_parameters" in reasoning and reasoning["missing_parameters"]:
                reasoning_section += "Missing Parameters:\n"
                for param in reasoning["missing_parameters"]:
                    reasoning_section += f"- {param}\n"
                reasoning_section += "\n"
                
            if "potential_challenges" in reasoning and reasoning["potential_challenges"]:
                reasoning_section += "Potential Challenges:\n"
                for challenge in reasoning["potential_challenges"]:
                    reasoning_section += f"- {challenge}\n"
                reasoning_section += "\n"
                
            if "recommended_approach" in reasoning:
                reasoning_section += f"Recommended Approach: {reasoning['recommended_approach']}\n\n"
        
        # Create learning section from past successes
        learning_section = ""
        if state.integration_type in self.learning_store:
            learning = self.learning_store[state.integration_type]
            learning_section = "Learned Best Practices for this Integration:\n"
            
            for practice in learning.get("best_practices", [])[:5]:  # Top 5 practices
                learning_section += f"- {practice}\n"
                
            for pattern in learning.get("successful_patterns", [])[:3]:  # Top 3 patterns
                learning_section += f"- Pattern: {pattern}\n"
        
        # Create script requirements section
        requirements_section = f"""
Script Requirements:
1. Create a well-structured {script_language} script for {state.action} of {state.integration_type}
2. Include robust error handling throughout the script
3. Validate all input parameters before proceeding
4. Include detailed logging of all actions
5. Create backup of any important files before modifying
6. Implement proper cleanup in case of failures
7. Add comments explaining complex or important sections
8. Return appropriate exit codes (0 for success, non-zero for failure)
9. Include a verification step at the end to confirm success
10. Handle all edge cases and potential errors gracefully
"""

        if script_language == "PowerShell":
            requirements_section += """
PowerShell Specific Requirements:
1. Use proper PowerShell error handling with try/catch blocks
2. Set $ErrorActionPreference = "Stop" at the beginning
3. Use PowerShell native commands instead of cmd.exe commands when possible
4. Use Write-Host for user output and Write-Error for errors
5. Check for administrator privileges when needed
6. Use proper PowerShell parameter validation
7. Include timestamps in log messages
"""
        else:
            requirements_section += """
Bash Specific Requirements:
1. Start with #!/bin/bash and set -e to exit on error
2. Use proper bash function definitions for modularity
3. Implement error handling with trap statements
4. Use proper variable quoting and escaping
5. Check for root privileges when needed with id -u
6. Use proper exit codes for different error scenarios
7. Include timestamps in log messages
"""

        # Combine all sections to create the final prompt
        prompt = f"""
You are tasked with creating a {script_language} script to {state.action} the New Relic {state.integration_type} integration on the target system.

{platform_section}

{params_section}

{docs_section}

{reasoning_section}

{learning_section}

{requirements_section}

Respond with ONLY the {script_language} script content, no introduction or explanations outside the script.
"""

        return prompt

    async def _generate_script_content(
        self, 
        prompt: str, 
        state: WorkflowState, 
        script_language: str
    ) -> str:
        """
        Generate script content using LLM.
        
        Args:
            prompt: Generation prompt
            state: Current workflow state
            script_language: Script language
            
        Returns:
            Generated script content
        """
        # Create system prompt
        system_prompt = f"""
You are an expert DevOps engineer with deep knowledge of New Relic integrations.
You specialize in creating robust, production-quality {script_language} scripts.

Your task is to write a detailed, comprehensive script that implements the requested action
for the specified New Relic integration. Make the script as robust and safe as possible.

Key requirements:
- Write ONLY the script itself, no explanations before or after
- Include robust error handling
- Add informative logging and output
- Implement proper validation for all inputs
- Apply best practices for {script_language} scripting
- Provide proper exit codes
- Create a complete, standalone solution

Return the script content directly without markdown code blocks or any other formatting.
"""

        try:
            # Generate script with LLM
            script_content = await self.llm_service.generate_code(
                prompt=prompt,
                system_prompt=system_prompt,
                language="powershell" if script_language == "PowerShell" else "bash",
                temperature=0.2,  # Lower temperature for more deterministic output
                context={
                    "integration_type": state.integration_type,
                    "action": state.action,
                    "platform": state.system_context.get('platform', {})
                }
            )
            
            return script_content
            
        except Exception as e:
            logger.error(f"Error in LLM script generation: {e}")
            raise ScriptError(f"Failed to generate script: {str(e)}")

    async def _post_process_script(self, script_content: str, state: WorkflowState, script_language: str) -> str:
        """
        Post-process script with enhancements and adaptations.
        
        Args:
            script_content: Raw script content
            state: Current workflow state
            script_language: Script language
            
        Returns:
            Enhanced script content
        """
        enhanced_script = script_content
        
        # Add header with generation information
        header = f"""# {script_language} script for {state.target_name} ({state.integration_type})
# Action: {state.action}
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# State ID: {state.state_id}
"""

        # Add tracking functions for better change management
        if script_language == "PowerShell":
            tracking_functions = """
# Change tracking functions
function Register-Change {
    param(
        [string]$Type,
        [string]$Target,
        [bool]$Revertible = $true,
        [string]$RevertCommand = "",
        [string]$BackupFile = $null
    )
    
    Write-Host "CHANGE_TRACKING: $Type | $Target | $Revertible | $RevertCommand | $BackupFile"
    
    # Change tracking marker for workflow agent
    $change = @{
        "type" = $Type
        "target" = $Target
        "revertible" = $Revertible
        "revert_command" = $RevertCommand
        "backup_file" = $BackupFile
    }
    
    $changeJson = ConvertTo-Json -Compress $change
    Write-Host "CHANGE_JSON_BEGIN $changeJson CHANGE_JSON_END"
}

function Backup-File {
    param(
        [string]$Path,
        [string]$BackupDir = "$env:TEMP\\backups"
    )
    
    if (-not (Test-Path $Path)) {
        Write-Host "No file to backup at $Path"
        return $null
    }
    
    # Create backup directory if it doesn't exist
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $filename = Split-Path -Leaf $Path
    $backupPath = "$BackupDir\\${filename}_$timestamp.bak"
    
    Copy-Item -Path $Path -Destination $backupPath -Force
    Write-Host "Created backup: $backupPath"
    
    return $backupPath
}

"""
        else:  # Bash
            tracking_functions = """
# Change tracking functions
register_change() {
    local change_type="$1"
    local target="$2"
    local revertible="${3:-true}"
    local revert_command="$4"
    local backup_file="$5"
    
    echo "CHANGE_TRACKING: $change_type | $target | $revertible | $revert_command | $backup_file"
    
    # Change tracking marker for workflow agent
    local change_json="{\\\"type\\\":\\\"$change_type\\\",\\\"target\\\":\\\"$target\\\",\\\"revertible\\\":$revertible,\\\"revert_command\\\":\\\"$revert_command\\\",\\\"backup_file\\\":\\\"$backup_file\\\"}"
    echo "CHANGE_JSON_BEGIN $change_json CHANGE_JSON_END"
}

backup_file() {
    local path="$1"
    local backup_dir="${2:-/tmp/backups}"
    
    if [[ ! -f "$path" ]]; then
        echo "No file to backup at $path"
        return 1
    fi
    
    # Create backup directory if it doesn't exist
    mkdir -p "$backup_dir"
    
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local filename=$(basename "$path")
    local backup_path="${backup_dir}/${filename}_${timestamp}.bak"
    
    cp "$path" "$backup_path"
    echo "Created backup: $backup_path"
    
    echo "$backup_path"
}

"""

        # Only add tracking functions if they don't already exist in the script
        if "Register-Change" not in enhanced_script and "register_change" not in enhanced_script:
            enhanced_script = header + tracking_functions + enhanced_script
        else:
            enhanced_script = header + enhanced_script
        
        # Add tracking calls for common operations if not already present
        if script_language == "PowerShell":
            # File creation tracking
            if "New-Item" in enhanced_script and "Register-Change" not in enhanced_script:
                enhanced_script = re.sub(
                    r"(New-Item\s+(?:-ItemType\s+\w+\s+)?-Path\s+[\"'])([^\"']+)([\"'])",
                    r"\1\2\3\nRegister-Change -Type 'file_created' -Target \2",
                    enhanced_script
                )
                
            # File modification tracking
            if "Set-Content" in enhanced_script and "Register-Change" not in enhanced_script:
                enhanced_script = re.sub(
                    r"(Set-Content\s+-Path\s+[\"'])([^\"']+)([\"'])",
                    r"$backupPath = Backup-File -Path \2\n\1\2\3\nRegister-Change -Type 'file_modified' -Target \2 -BackupFile $backupPath",
                    enhanced_script
                )
        else:  # Bash
            # File creation tracking
            if "touch" in enhanced_script and "register_change" not in enhanced_script:
                enhanced_script = re.sub(
                    r"(touch\s+)([\"']?)([^\"']+)([\"']?)",
                    r"\1\2\3\4\nregister_change 'file_created' '\3'",
                    enhanced_script
                )
                
            # File modification tracking
            if " > " in enhanced_script and "register_change" not in enhanced_script:
                enhanced_script = re.sub(
                    r"(.*?>[ \t]+)([\"']?)([^\"']+)([\"']?)",
                    r"backup_path=$(backup_file \3)\n\1\2\3\4\nregister_change 'file_modified' '\3' true '' \"$backup_path\"",
                    enhanced_script
                )
        
        return enhanced_script

    async def _save_script_to_file(self, script_content: str, state: WorkflowState, script_language: str) -> Path:
        """
        Save generated script to file with metadata.
        
        Args:
            script_content: Script content
            state: Current workflow state
            script_language: Script language
            
        Returns:
            Path to saved script
        """
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create sanitized filename
        sanitized_target = re.sub(r'[^\w\-\.]', '_', state.target_name)
        
        # Determine file extension
        ext = ".ps1" if script_language == "PowerShell" else ".sh"
        
        # Create filename
        filename = f"{sanitized_target}_{state.action}_{timestamp}{ext}"
        
        # Full path
        script_path = self.script_dir / filename
        
        # Save script
        with open(script_path, "w") as f:
            f.write(script_content)
        
        # Create metadata file
        metadata = {
            "script_path": str(script_path),
            "state_id": str(state.state_id),
            "action": state.action,
            "integration_type": state.integration_type,
            "target_name": state.target_name,
            "script_language": script_language,
            "parameters": state.parameters,
            "platform": state.system_context.get('platform', {}),
            "generated_at": timestamp,
            "size_bytes": len(script_content)
        }
        
        metadata_path = script_path.with_suffix(".meta.json")
        
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved script to {script_path} with metadata")
        
        return script_path

    def _get_cache_key(self, state: WorkflowState) -> str:
        """
        Generate a cache key for a state.
        
        Args:
            state: Workflow state
            
        Returns:
            Cache key
        """
        # Create key components
        components = [
            state.action,
            state.integration_type,
            state.target_name,
            json.dumps(state.parameters, sort_keys=True)
        ]
        
        # Add platform info
        platform = state.system_context.get('platform', {})
        if platform:
            components.append(platform.get('system', ''))
            components.append(platform.get('distribution', ''))
        
        # Create hash
        key = hashlib.md5('|'.join(components).encode()).hexdigest()
        
        return f"script_{state.integration_type}_{state.action}_{key[:8]}"

    def _update_script_cache(self, key: str, entry: Dict[str, Any]) -> None:
        """
        Update script cache with a new entry.
        
        Args:
            key: Cache key
            entry: Cache entry
        """
        self.script_cache[key] = entry
        
        # Limit cache size
        max_cache_size = self.config.get("max_cache_size", 100)
        
        if len(self.script_cache) > max_cache_size:
            # Remove oldest entries
            sorted_keys = sorted(
                self.script_cache.keys(),
                key=lambda k: self.script_cache[k].get("generated_at", "")
            )
            
            # Remove oldest entries
            for old_key in sorted_keys[:len(self.script_cache) - max_cache_size]:
                del self.script_cache[old_key]
                
        logger.debug(f"Updated script cache, now contains {len(self.script_cache)} entries")

    def _add_generation_metadata(self, state: WorkflowState, reasoning: Dict[str, Any]) -> WorkflowState:
        """
        Add script generation metadata to state.
        
        Args:
            state: Current workflow state
            reasoning: Generation reasoning
            
        Returns:
            Updated workflow state
        """
        # Create a copy of template data
        template_data = dict(state.template_data or {})
        
        # Add script generation info
        template_data["script_generation"] = {
            "timestamp": datetime.now().isoformat(),
            "reasoning": reasoning,
            "llm_provider": self.llm_service.default_provider
        }
        
        # Update state
        return state.evolve(template_data=template_data)

    async def update_learning_from_execution(self, state: WorkflowState, success: bool) -> None:
        """
        Update learning from execution results.
        
        Args:
            state: Workflow state after execution
            success: Whether execution was successful
        """
        if not state.script:
            return
            
        if success:
            # Learn from successful scripts
            integration_type = state.integration_type
            
            if integration_type not in self.learning_store:
                self.learning_store[integration_type] = {
                    "best_practices": [],
                    "successful_patterns": [],
                    "execution_count": 0,
                    "success_count": 0
                }
                
            # Update counters
            self.learning_store[integration_type]["execution_count"] += 1
            self.learning_store[integration_type]["success_count"] += 1
            
            # Extract patterns from successful script
            await self._extract_patterns_from_script(state.script, integration_type)
            
        else:
            # Update failure stats
            integration_type = state.integration_type
            
            if integration_type in self.learning_store:
                self.learning_store[integration_type]["execution_count"] += 1
                
        logger.debug(f"Updated learning store for {state.integration_type}, success={success}")

    async def _extract_patterns_from_script(self, script: str, integration_type: str) -> None:
        """
        Extract patterns from successful script using LLM.
        
        Args:
            script: Successful script
            integration_type: Integration type
        """
        prompt = f"""
        Analyze this successful script for a New Relic {integration_type} integration and identify best practices and patterns.
        
        SCRIPT:
        ```
        {script[:3000]}  # Limit to first 3000 chars
        ```
        
        Extract:
        1. 3-5 best practices demonstrated in this script
        2. 2-3 successful patterns that could be applied to other {integration_type} integrations
        
        Format your response as JSON with two arrays: "best_practices" and "successful_patterns".
        """
        
        try:
            json_response = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt="You are an expert at analyzing scripts and identifying best practices and patterns.",
                temperature=0.3
            )
            
            # Extract patterns
            best_practices = json_response.get("best_practices", [])
            successful_patterns = json_response.get("successful_patterns", [])
            
            # Update learning store
            if integration_type in self.learning_store:
                # Append unique practices
                for practice in best_practices:
                    if practice not in self.learning_store[integration_type]["best_practices"]:
                        self.learning_store[integration_type]["best_practices"].append(practice)
                
                # Append unique patterns
                for pattern in successful_patterns:
                    if pattern not in self.learning_store[integration_type]["successful_patterns"]:
                        self.learning_store[integration_type]["successful_patterns"].append(pattern)
                
                logger.debug(f"Updated learning store with {len(best_practices)} practices and {len(successful_patterns)} patterns")
                
        except Exception as e:
            logger.warning(f"Error extracting patterns from script: {e}")
