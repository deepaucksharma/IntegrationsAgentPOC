# Workflow Agent Integration Framework

## Documentation Contents

This documentation is structured across several focused README files:

1.  **[Architecture Overview](architecture-readme.md)**: System architecture, component relationships, and design patterns
2.  **[LLM & Agent System](llm-agents-readme.md)**: The multi-agent system and AI-driven components
3.  **[Component Hierarchy](component-hierarchy-readme.md)**: Detailed breakdown of system modules and their responsibilities
4.  **[Data Flow](data-flow-readme.md)**: Information flow throughout the workflow lifecycle
5.  **[Developer Setup & Troubleshooting](developer-readme.md)**: Setup instructions, common issues, and debugging tips
6.  **[Recent Fixes & Improvements](FIXED.md)**: Summary of critical issues addressed in recent updates
7.  **[Cleanup Notes](docs/CLEANUP-NOTES.md)**: Documentation of recent code cleanup and refactoring efforts

## Recent Code Improvements

The codebase has undergone significant improvements to enhance maintainability and reduce redundancy:

1. **Consolidated Agent Implementation**: Unified the base agent classes into a single implementation supporting both standalone and message bus paradigms
2. **Enhanced Change Tracking**: Added dedicated `ChangeTracker` for more reliable system change detection and rollback
3. **Optimized Service Container**: Improved service registration with consolidated methods and better error handling
4. **Improved Integration Registry**: Added duplicate detection to prevent redundant integration registrations
5. **Verification Analysis Consolidation**: Centralized LLM-driven analysis for consistent verification outcomes

See the [Cleanup Notes](docs/CLEANUP-NOTES.md) for detailed information about these changes.

## Agentic Workflow 

The following demonstrates a typical workflow with agents:

```
┌──────────────┐          ┌───────────────┐             ┌───────────────┐
│              │          │               │             │               │
│ CLI/API      │ ────────►│ Coordinator   │────────────►│ Knowledge     │
│ Interface    │          │ Agent         │◄───────────┐│ Agent         │
│              │◄─────────│               │             │               │
└──────────────┘          └───────┬───────┘             └───────────────┘
                                  │
                                  ▼
                          ┌───────────────┐             ┌───────────────┐
                          │               │             │               │
                          │ Script        │────────────►│ Execution     │
                          │ Builder       │◄───────────┐│ Agent         │
                          │               │             │               │
                          └───────────────┘             └───────────────┘
```

---

## Enhanced Security and Reliability Architecture

The system has been redesigned with a focus on security, reliability, and recovery:

### 1. Enhanced Security Architecture
- **Multi-Layered Script Validation**: Comprehensive validation with static analysis, syntax checking, and security pattern detection
- **Least Privilege Execution**: Configurable isolation methods with privilege restrictions
- **Secure Template Handling**: Template validation and sandboxed rendering

### 2. Robust State Management
- **Immutable State Transitions**: Carefully tracked workflow progression with immutable state changes
- **Comprehensive Checkpointing**: Sequential checkpoints at every stage to enable recovery
- **Transparent Change Tracking**: Detailed tracking of all system modifications for reliable rollback

### 3. Advanced Recovery System
- **Tiered Recovery Strategies**: Multiple fallback mechanisms for maximum resilience
- **Verification-Based Rollback**: Post-rollback verification ensures system integrity
- **Transaction-Based Operations**: All operations are transactional with proper audit trails

---

## Configuration-Controlled Template Behavior

### 1. Multi-Level Template Resolution

```python
@root_validator(pre=True)
def resolve_workspace_paths(cls, values: Dict[str, Any]) -> Dict[str, Any]:
    workspace_root = os.environ.get("WORKSPACE_ROOT", os.getcwd())
    return { key: value.replace("${WORKSPACE_ROOT}", workspace_root)
             if isinstance(value, str) and "${WORKSPACE_ROOT}" in value else value
             for key, value in values.items() }
```

- **Dynamic resolution** for workspace-relative paths.
- Supports customer overrides.

### 2. Template Search Path Prioritization

Search order:
1. Custom customer templates (if provided)
2. Integration‑specific templates
3. Common templates for the integration type
4. Default base templates
5. Inline fallback templates

*This ensures a graceful fallback if higher‑priority templates are missing.*

### Dynamic Template Enhancement

1. **Documentation Parsing:** Uses aiohttp/BeautifulSoup to extract:
   - Prerequisites
   - Installation methods
   - Configuration options
   - Verification steps
2. **Knowledge Integration:** Filters docs by platform.
3. **Strategy Agent:** Scores methods (platform match, complexity, etc.) and selects the best.
4. **Dynamic Script Generation:** Creates custom scripts based on the above.
5. **Self‑Improving Verification:** Incorporates verification feedback for continuous improvement.

---

## Key Code Snippets

### Improved Script Security Validation

```python
def validate_script_security(script_content: str) -> Dict[str, Any]:
    """
    Validate script content for potentially dangerous operations using multiple methods.
    """
    warnings = []
    errors = []
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, script_content, re.IGNORECASE):
            errors.append(f"Dangerous pattern detected: {pattern}")
    
    # Apply static analysis when available
    if "#!/bin/bash" in script_content or "#!/bin/sh" in script_content:
        with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as temp:
            temp_path = temp.name
            temp.write(script_content.encode())
        
        try:
            # Run shellcheck to find issues
            result = subprocess.run(
                ["shellcheck", "-f", "json", temp_path],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0:
                logger.debug("Shellcheck validation passed")
            else:
                try:
                    shellcheck_output = json.loads(result.stdout)
                    for issue in shellcheck_output:
                        level = issue.get("level", "").lower()
                        message = issue.get("message", "")
                        
                        if level == "error":
                            errors.append(f"Shellcheck error: {message}")
                        else:
                            warnings.append(f"Shellcheck warning: {message}")
                except json.JSONDecodeError:
                    warnings.append("Failed to parse shellcheck output")
        finally:
            os.unlink(temp_path)
    
    # Determine overall validity
    valid = len(errors) == 0
    
    return {
        "valid": valid,
        "warnings": warnings,
        "errors": errors
    }
```

### Enhanced Change Tracking for Reliable Rollback

```python
def extract_changes(self, output: str) -> List[Change]:
    """
    Extract changes from script output using the consolidated ChangeTracker.
    
    Args:
        output: Script output to parse
        
    Returns:
        List of Change objects
    """
    # Using the consolidated ChangeTracker
    from .change_tracker import ChangeTracker
    tracker = ChangeTracker()
    return tracker.extract_changes(output)
```

---

## API Key Configuration

The workflow agent supports LLM-based script generation which requires an OpenAI API key. There are two ways to provide the API key:

1. **Environment Variable (Recommended)**
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

2. **Configuration File**
   ```yaml
   # workflow_config.yaml
   openai_api_key: your_api_key_here
   ```

The environment variable takes precedence over the configuration file. If no API key is provided, the system will fall back to template-based script generation.

### API Key Priority Order
1. Environment variable (`OPENAI_API_KEY`)
2. Configuration file (`openai_api_key` in workflow_config.yaml)
3. Fallback to template-based generation if no key is available

For security best practices:
- Use environment variables in production environments
- Never commit API keys to version control
- Use separate API keys for development and production
- Rotate API keys periodically

## Code Structure

The project follows a modular architecture with the following key components:

- **agent**: Base agent implementations and agent-related functionality
- **core**: Core functionality including state management and service container
- **execution**: Script execution and change tracking
- **integrations**: Integration definitions and registration
- **llm**: LLM service integration and prompt handling
- **templates**: Template rendering and management
- **verification**: Verification steps and analysis

Recent restructuring has consolidated several components to reduce redundancy and improve maintainability. See the [Cleanup Notes](docs/CLEANUP-NOTES.md) for details.
