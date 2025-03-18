# Workflow Agent

A Python framework for orchestrating multi-step workflows with AI-driven adaptation and self-improvement capabilities, featuring dynamic documentation-based integration.

## Overview

The Workflow Agent provides a robust system for managing complex installation, removal, and verification workflows using a multi-agent architecture. It features:

- Dynamic integration using documentation parsing and interpretation
- Intelligent installation strategy selection
- Platform-aware script generation
- Comprehensive verification system
- Data-driven integration using YAML definitions
- Safe script execution with Docker isolation
- Automatic failure analysis and self-improvement
- Comprehensive logging and execution history

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/workflow-agent.git
cd workflow-agent

# Install the package
pip install -e .
```

## Usage

### Command Line Interface

```bash
# Install an integration
workflow-agent install infra_agent --license-key=YOUR_LICENSE_KEY --host=YOUR_HOST

# Remove an integration
workflow-agent remove infra_agent

# Verify an integration
workflow-agent verify infra_agent
```

### Programmatic Usage

```python
import asyncio
from workflow_agent.core.message_bus import MessageBus
from workflow_agent.multi_agent.coordinator import CoordinatorAgent
from workflow_agent.documentation.parser import DocumentationParser
from workflow_agent.knowledge.integration import DynamicIntegrationKnowledge
from workflow_agent.strategy.installation import InstallationStrategyAgent
from workflow_agent.scripting.dynamic_generator import DynamicScriptGenerator
from workflow_agent.verification.dynamic import DynamicVerificationBuilder

async def run_workflow():
    # Set up multi-agent system
    message_bus = MessageBus()
    coordinator = CoordinatorAgent(message_bus)
    
    # Initialize dynamic components
    doc_parser = DocumentationParser()
    knowledge = DynamicIntegrationKnowledge(doc_parser)
    strategy = InstallationStrategyAgent()
    script_generator = DynamicScriptGenerator()
    verification_builder = DynamicVerificationBuilder()
    
    # Define workflow state
    state = {
        "action": "install",
        "target_name": "monitoring_agent",
        "integration_type": "infra_agent",
        "parameters": {
            "license_key": "YOUR_LICENSE_KEY",
            "host": "your.host.com"
        },
        "system_context": {
            "platform": {
                "system": "linux",
                "distribution": "ubuntu",
                "version": "20.04"
            }
        }
    }
    
    # Execute dynamic workflow
    try:
        # Enhance state with documentation knowledge
        state = await knowledge.enhance_workflow_state(state)
        
        # Determine best installation strategy
        state = await strategy.determine_best_approach(state)
        
        # Generate installation script
        install_script = await script_generator.generate_from_knowledge(state)
        
        # Generate verification script
        verify_script = await verification_builder.build_verification_script(state)
        
        # Execute scripts (using your execution system)
        result = await coordinator.execute_scripts(install_script, verify_script)
        
        print(f"Workflow completed with result: {result}")
        
    except Exception as e:
        print(f"Workflow failed: {e}")

# Run the workflow
asyncio.run(run_workflow())
```

## Architecture

The system uses a dynamic documentation-based architecture with these key components:

### Documentation Processing
- **DocumentationParser**: Fetches and parses integration documentation from sources
  - Extracts prerequisites, installation methods, and verification steps
  - Handles different documentation formats and structures
  - Provides structured knowledge for decision-making

### Knowledge Management
- **DynamicIntegrationKnowledge**: Enhances workflow state with documentation data
  - Filters information based on platform compatibility
  - Normalizes system-specific requirements
  - Maintains context for decision-making

### Installation Strategy
- **InstallationStrategyAgent**: Determines optimal installation approach
  - Scores methods based on platform compatibility
  - Considers complexity and prerequisites
  - Evaluates reliability of different approaches
  - Adapts to system constraints

### Script Generation
- **DynamicScriptGenerator**: Creates installation scripts dynamically
  - Generates platform-specific commands
  - Includes prerequisite checks
  - Handles error cases
  - Provides progress feedback

### Verification System
- **DynamicVerificationBuilder**: Builds comprehensive verification
  - Creates platform-aware verification scripts
  - Includes service and process checks
  - Validates configuration
  - Performs port availability testing

## Configuration

Configuration is managed through YAML files. Default locations:
- `./workflow_config.yaml`
- `~/.workflow_agent/config.yaml`

```yaml
configurable:
  user_id: "test_user"
  template_dir: "./integrations/common_templates"
  use_isolation: true
  isolation_method: "docker"  # or "direct"
  execution_timeout: 30000
  skip_verification: false
  rule_based_optimization: true
  use_static_analysis: true
  db_connection_string: "workflow_history.db"
  prune_history_days: 90
  max_concurrent_tasks: 5
  least_privilege_execution: true
  log_level: "INFO"
  
  # Dynamic workflow settings
  documentation:
    base_url: "https://docs.newrelic.com/install/"
    cache_ttl: 3600  # Cache documentation for 1 hour
    max_retries: 3   # Number of fetch retries
    
  strategy:
    scoring_weights:
      platform_match: 5.0
      complexity: 3.0
      prerequisites: 2.0
      reliability: 4.0
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run the example workflow
python examples/test_workflow.py
```

## Adding New Documentation Sources

The system can be extended to support additional documentation sources:

1. Create a new parser class inheriting from `DocumentationParser`
2. Implement the source-specific parsing logic
3. Register the parser in the configuration

Example:

```python
from workflow_agent.documentation.parser import DocumentationParser

class CustomDocParser(DocumentationParser):
    async def fetch_integration_docs(self, integration_type):
        # Implement custom documentation fetching
        pass
        
    def _extract_structured_knowledge(self, content):
        # Implement custom parsing logic
        pass
```

## License

MIT License