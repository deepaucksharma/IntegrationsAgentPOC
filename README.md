Below is a detailed README.md file tailored for the Workflow Agent project. It provides instructions to set up, run, and generate scripts for all supported integrations (currently just InfraAgentIntegration, as it’s the only one in the provided codebase). The README assumes a user wants to explore the framework’s capabilities, focusing on script generation, and includes prerequisites, installation steps, configuration details, and examples.

Workflow Agent
A Python framework for orchestrating multi-step workflows with AI-driven adaptation, script generation, execution, validation, and rollback capabilities.

Overview
The Workflow Agent is designed to automate complex workflows by generating, validating, and executing scripts based on templates or integration handlers. It supports isolation (e.g., Docker), resource management, execution history tracking, and automatic rollback on failure. This README guides you through setting up the project and generating scripts for all supported integrations.

Features
Script Generation: Generate Bash scripts from Jinja2 templates or integration handlers.
Validation: Validate scripts for security and correctness using static analysis (e.g., ShellCheck).
Execution: Run scripts with isolation (Docker or direct) and resource limits.
Verification: Check execution results for success.
Rollback: Automatically revert changes on failure.
History: Store execution details in a SQLite database.
Supported Integrations
Currently, the only built-in integration is:

InfraAgentIntegration: Handles infrastructure monitoring agent tasks (e.g., monitoring_agent, infra_agent, metrics_agent) with actions like install, remove, and verify.
Prerequisites
Python: Version 3.8 or higher.
Operating System: Linux/macOS (Windows support is partial due to Bash script reliance).
Docker: Optional, for isolated execution (install via Docker's official guide).
ShellCheck: Optional, for static script analysis (install via sudo apt install shellcheck on Ubuntu or equivalent).
Installation
Clone the Repository

bash

Collapse

Wrap

Copy
git clone <repository-url>
cd workflow-agent
Set Up a Virtual Environment

bash

Collapse

Wrap

Copy
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install Dependencies

Use the provided requirements.txt:
bash

Collapse

Wrap

Copy
pip install -r requirements.txt
For development tools (e.g., black, pylint, shellcheck-py):
bash

Collapse

Wrap

Copy
pip install -e ".[dev]"
Note: If you plan to use ShellCheck, ensure shellcheck-py is installed and ShellCheck is available on your system.

Verify Installation

bash

Collapse

Wrap

Copy
python -c "import workflow_agent; print(workflow_agent.__version__)"
Output should be 0.2.0.

Configuration
The project uses a workflow_config.yaml file for settings. A default is provided, but you can customize it.

Default Configuration (workflow_config.yaml)
yaml

Collapse

Wrap

Copy
configurable:
  user_id: "test_user"
  template_dir: "./templates"
  custom_template_dir: "./custom_templates"
  use_isolation: true
  isolation_method: "docker"
  execution_timeout: 30000
  skip_verification: false
  rule_based_optimization: true
  use_static_analysis: true
  db_connection_string: "workflow_history.db"
  prune_history_days: 90
  plugin_dirs:
    - "./plugins"
  max_concurrent_tasks: 5
  least_privilege_execution: true
  log_level: "INFO"
Key Settings
use_isolation: Set to false to run scripts directly (faster for testing, requires no Docker).
isolation_method: Options are docker, chroot, venv, direct, or none (only docker and direct are fully implemented).
log_level: Set to DEBUG for verbose output.
template_dir: Directory for Jinja2 templates (create if using custom templates).
To override the default config, set the WORKFLOW_CONFIG_PATH environment variable:

bash

Collapse

Wrap

Copy
export WORKFLOW_CONFIG_PATH="/path/to/custom_config.yaml"
Running the Project
Generating Scripts for All Supported Integrations
The InfraAgentIntegration supports targets monitoring_agent, infra_agent, and metrics_agent with actions install, remove, and verify. Below is a Python script to generate scripts for all combinations.

Create a Script (generate_scripts.py) Save this in the project root:
python

Collapse

Wrap

Copy
import asyncio
import yaml
import logging
from src.workflow_agent.agent import WorkflowAgent
from src.workflow_agent.utils.logging import setup_logging

async def generate_scripts():
    # Load configuration
    with open("workflow_config.yaml", "r") as f:
        config = yaml.safe_load(f)
    config["configurable"]["use_isolation"] = False  # Speed up for demo
    config["configurable"]["log_level"] = "DEBUG"

    # Set up logging
    setup_logging(log_level=config["configurable"]["log_level"])

    # Targets and actions for InfraAgentIntegration
    targets = ["monitoring_agent", "infra_agent", "metrics_agent"]
    actions = ["install", "remove", "verify"]
    integration_type = "infra_agent"

    agent = WorkflowAgent()
    await agent.initialize(config)

    for target in targets:
        for action in actions:
            # Define input state
            state = {
                "action": action,
                "target_name": target,
                "integration_type": integration_type,
                "parameters": {
                    "license_key": "test_license_123",
                    "endpoint": "https://example-metrics.com"
                }
            }
            print(f"\nGenerating script for {target} - {action}")
            result = await agent.invoke(state, config)
            if "script" in result:
                print(f"Generated Script:\n{result['script']}\n")
            elif "error" in result:
                print(f"Error: {result['error']}")
            else:
                print("No script generated, check logs.")

    await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(generate_scripts())
Run the Script
bash

Collapse

Wrap

Copy
python generate_scripts.py
Output: The script will print generated Bash scripts for each target-action pair (e.g., monitoring_agent-install, infra_agent-remove). Errors, if any, will be logged with details.
What Happens
The WorkflowAgent.invoke method processes the input state:
Validates parameters (e.g., license_key is required).
Generates a script via InfraAgentIntegration.handle.
Validates the script (e.g., checks for shebang, dangerous patterns).
Executes it (skipped here since use_isolation=false and we’re focusing on generation).
Scripts are tailored to the target and action, with system detection (e.g., Debian vs. RHEL).
Customizing Templates
To use custom templates instead of the integration handler:

Create a templates directory:
bash

Collapse

Wrap

Copy
mkdir templates
Add a template (e.g., monitoring_agent-install.j2):
bash

Collapse

Wrap

Copy
#!/usr/bin/env bash
set -e
echo "Custom install for {{ target_name }}"
echo "License: {{ parameters.license_key }}"
Update state in generate_scripts.py to remove integration_type or set it to an unrecognized value, forcing template fallback.
Troubleshooting
No Script Generated: Check logs (set log_level: "DEBUG") for template or integration errors.
Permission Denied: Ensure the script directory is writable and Docker (if used) is running.
ShellCheck Errors: Install shellcheck-py and ShellCheck if static analysis fails.
Database Issues: Verify workflow_history.db is writable; delete it to reset history.
Testing
Run the included test script:

bash

Collapse

Wrap

Copy
python test_workflow.py
Tests monitoring_agent installation with a mock license_key.
Modify use_isolation in the config for faster runs.