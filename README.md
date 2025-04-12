# IntegrationsAgentPOC

Proof of concept for an agentic integration workflow system using LLMs and multi-agent architectures.

## Overview

This project demonstrates an LLM-powered, multi-agent system for automating the installation, verification, and uninstallation of monitoring integrations. It leverages multiple specialized agents that collaborate to:

1. **Knowledge Retrieval**: Gather integration-specific requirements and procedures
2. **Script Generation**: Create installation/verification/uninstallation scripts
3. **Execution**: Run scripts safely with change tracking and isolation
4. **Verification**: Validate successful integration
5. **Recovery**: Implement fallback mechanisms when operations fail

## Getting Started

### Prerequisites

- Python 3.10+
- PowerShell 5.1+ (for Windows scripts)
- Bash (for Linux/Unix scripts)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/IntegrationsAgentPOC.git
   cd IntegrationsAgentPOC
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/MacOS
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the package in development mode:
   ```bash
   pip install -e .
   ```

### Configuration

Create a `workflow_config.yaml` file or use the provided example:

```yaml
# Basic configuration
log_level: INFO
template_dir: ./templates
script_dir: ./generated_scripts

# Security settings
security:
  least_privilege_execution: true
  verify_recoveries: true

# Execution settings
isolation_method: direct  # Options: direct, docker
use_llm: true
```

## Usage

### Running via PowerShell

```powershell
.\agentic_workflow.ps1 -Action install -IntegrationType infra_agent -LicenseKey "your-license-key"
```

### Running via Python

```bash
python -m workflow_agent install infra_agent --license-key "your-license-key" --host "localhost"
```

### Standalone Example

For a quick demo, run the standalone example:

```bash
python examples/standalone_infra_agent.py --action install --license "your-license-key"
```

## Project Structure

```
IntegrationsAgentPOC/
├── src/workflow_agent/           # Main package
│   ├── agent/                    # Agent implementations
│   ├── core/                     # Core framework components
│   ├── execution/                # Script execution with isolation
│   ├── multi_agent/              # Multi-agent coordination
│   ├── templates/                # Template handling
│   ├── verification/             # Result verification
│   └── utils/                    # Utility functions
├── templates/                    # Script templates
├── plugins/                      # Integration plugins
├── examples/                     # Example scripts
├── docs/                         # Documentation
├── generated_scripts/            # Output directory for scripts
└── tests/                        # Test suite
```

## Documentation

For more detailed information, refer to:
- [Documentation Index](docs/INDEX.md)
- [Architecture Overview](docs/architecture-readme.md)
- [Code Standards](docs/code_standards.md)
- [Plugin Development](plugins/README.md)
- [Template Development](templates/README.md)
- [Refactoring Implementation](README-refactoring.md)

## Development Workflow

When developing new features or fixing bugs:

1. Create a feature branch from `main`
2. Make your changes, following the [code standards](docs/code_standards.md)
3. Add tests for your changes
4. Run tests to ensure all tests pass
5. Submit a pull request

## Maintenance

To clean up the project directories and archive old files:

```powershell
.\cleanup_script.ps1
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
