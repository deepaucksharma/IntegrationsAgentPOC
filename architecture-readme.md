# Architecture Overview

The Workflow Agent framework is built on a modular, message-driven architecture.  This design promotes extensibility, robustness, and maintainability.  Key features include asynchronous operation, a clear separation of concerns, dynamic integration loading, and support for various execution environments.

## Navigation

-   [Overview](README.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Component Hierarchy](component-hierarchy-readme.md)
-   [Data Flow](data-flow-readme.md)
-   [Developer Setup & Troubleshooting](developer-readme.md)

## Architectural Components

The system comprises the following key components:

*   **User Interface (CLI/API)**: The entry point for users.  Commands are defined in [`src/workflow_agent/main.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/main.py).

*   **Workflow Agent (Main Controller)**: Orchestrates the overall workflow execution.  Also located in [`src/workflow_agent/main.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/main.py).

*   **Multi-Agent System**: A group of specialized agents that handle tasks like knowledge retrieval, script building, and execution.  See the [`src/workflow_agent/multi_agent`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/multi_agent) directory.

*   **Integration Registry**: Dynamically loads and manages integration plugins. See [`src/workflow_agent/integrations/registry.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/integrations/registry.py) and the [`src/workflow_agent/integrations`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/integrations) directory.

*   **Configuration Management**: Loads, validates, and manages system configurations.  See the [`src/workflow_agent/config`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/config) directory.  The primary configuration class is `WorkflowConfiguration` in [`src/workflow_agent/config/configuration.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/config/configuration.py).

*   **Dependency Container**: Manages dependencies between components.  See [`src/workflow_agent/core/container.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/core/container.py).

*   **Script Generator & Validator**: Generates and validates scripts.  See the [`src/workflow_agent/scripting`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/scripting) directory.  Key classes include `ScriptGenerator` ([`src/workflow_agent/scripting/generator.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/scripting/generator.py)) and `ScriptValidator` ([`src/workflow_agent/scripting/validator.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/scripting/validator.py)).

*   **Documentation Parser**: Extracts information from integration documentation. See [`src/workflow_agent/documentation/parser.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/documentation/parser.py).

*   **Execution Engine**: Executes generated scripts, supporting different isolation methods. See the [`src/workflow_agent/execution`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/execution) directory. Key classes: `ScriptExecutor` ([`src/workflow_agent/execution/executor.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/execution/executor.py)) and isolation methods in ([`src/workflow_agent/execution/isolation.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/execution/isolation.py)).

*   **Recovery Manager (Rollback)**: Handles error recovery and rollback. See [`src/workflow_agent/rollback`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/rollback) and specifically [`src/workflow_agent/recovery/manager.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/recovery/manager.py).

*   **Knowledge Base & Manager**: Stores and manages knowledge. See  [`src/workflow_agent/knowledge`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/knowledge) and the storage implementation in [`src/workflow_agent/storage/knowledge_base.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/storage/knowledge_base.py).

*   **Storage & History**:  Provides persistent storage for execution history and other data. See the [`src/workflow_agent/storage`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/storage) directory, including `ExecutionHistoryManager` in [`src/workflow_agent/storage/history.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/storage/history.py).

## Core Design Principles

The architecture is founded on these principles:

### 1. Separation of Concerns

Each component has a specific, well-defined responsibility, promoting modularity and maintainability. This is reflected in the project's directory structure.

### 2. Message-Driven Architecture

Components communicate asynchronously via a message bus ([`src/workflow_agent/core/message_bus.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/core/message_bus.py)). This decouples components, improving resilience and allowing for independent operation and scaling.

### 3. Immutable State Management

The `WorkflowState` object ([`src/workflow_agent/core/state.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/core/state.py)) is immutable. State changes result in new `WorkflowState` instances, creating a clear audit trail and facilitating concurrent operations.

### 4. Dynamic Discovery

Integrations are discovered and loaded dynamically.  This allows for easy extension without modifying core code. The `IntegrationRegistry` ([`src/workflow_agent/integrations/registry.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/integrations/registry.py)) and `IntegrationManager` ([`src/workflow_agent/integrations/manager.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/integrations/manager.py)) handle this.

## Technical Stack

-   **Python 3.8+**: The primary programming language.
-   **Pydantic**: For data validation, settings management, and defining data structures (e.g., `WorkflowState`, `WorkflowConfiguration`).
-   **AsyncIO**: For asynchronous programming, enabling concurrent execution.
-   **Jinja2**: For template-based script generation.
-   **SQLite**: For local data persistence (execution history).
-   **Docker**: For optional script execution isolation.
-   **aiohttp**: For asynchronous HTTP requests (used in documentation fetching).

Dependencies are listed in [`requirements.txt`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/requirements.txt).

## System Boundaries

The Workflow Agent interacts with the following external systems:

-   **User/Admin (CLI/API)**: Users interact via the command line.
-   **Workflow Agent Framework**: The core system described here.
-   **Target System (for execution)**: The system where scripts are run (server, VM, container).
-   **External Systems**:
    -   **Documentation Sites**:  Sources of integration information.
    -   **Package Managers**: (e.g., `apt`, `yum`, `choco`) on target systems.
    -   **Target Systems**: Systems where integrations are managed.

## Key Interfaces

The system has several key interfaces:

1.  **CLI/API Interface**: User interaction, defined in [`src/workflow_agent/main.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/main.py).
2.  **Integration Interface**:  The `IntegrationBase` class ([`src/workflow_agent/integrations/base.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/integrations/base.py)) defines how to add new integrations.
3.  **Documentation Interface**: The `DocumentationParser` ([`src/workflow_agent/documentation/parser.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/documentation/parser.py)) handles fetching documentation.
4.  **Execution Interface**: The `ScriptExecutor` ([`src/workflow_agent/execution/executor.py`](https://github.com/deepaucksharma/IntegrationsAgentPOC/blob/main/src/workflow_agent/execution/executor.py)) abstracts script execution.

For details on the multi-agent system, see [LLM & Agent System](llm-agents-readme.md).
