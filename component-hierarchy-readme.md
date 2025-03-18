# Component Hierarchy

This document outlines the hierarchical structure of the Workflow Agent framework's components and their relationships.

## Navigation

-   [Overview](overview-readme.md)
-   [Architecture Overview](architecture-readme.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Data Flow](data-flow-readme.md)
-   [Developer Setup & Troubleshooting](developer-readme.md)

## Component Tree

```
workflow_agent/
|
+-- core/                          # Core framework components
|   |-- state.py                   # Immutable state management
|   |-- message_bus.py             # Pub/sub communication
|   |-- container.py               # Dependency injection
|
+-- config/                        # Configuration management
|   |-- configuration.py           # Configuration validation
|   |-- loader.py                  # Config file loading
|   |-- templates.py               # Template management
|
+-- multi_agent/                   # Multi-agent system
|   |-- coordinator.py             # Central workflow orchestrator
|   |-- knowledge.py               # Documentation knowledge agent
|   |-- script_builder.py          # Script generation agent
|   |-- execution.py               # Script execution agent
|   |-- improvement.py             # Self-improvement agent
|
+-- integrations/                  # Integration plugins
|   |-- base.py                    # Base integration class
|   |-- registry.py                # Dynamic discovery
|   |-- common_templates/          # Shared templates
|   |   |-- install/               # Installation templates
|   |   |-- remove/                # Removal templates
|   |   |-- verify/                # Verification templates
|   |   |-- macros/                # Reusable template components
|
+-- documentation/                 # Documentation handling
|   |-- parser.py                  # Documentation parsing
|
+-- scripting/                     # Script generation
|   |-- generator.py               # Script generator
|   |-- validator.py               # Script validation
|   |-- dynamic_generator.py       # Dynamic script creation
|
+-- execution/                     # Script execution
|   |-- executor.py                # Script execution engine
|   |-- isolation.py               # Execution isolation methods
|
+-- storage/                       # Data persistence
|   |-- history.py                 # Execution history
|   |-- knowledge_base.py          # Knowledge storage
|
+-- strategy/                      # Decision strategies
|   |-- installation.py            # Installation strategy selection
|
+-- rollback/                      # Error recovery
|   |-- recovery.py                # Rollback management
|
+-- verification/                  # Result verification
|   |-- verifier.py                # Verification engine
|   |-- dynamic.py                 # Dynamic verification building
|
+-- error/                         # Error handling
|   |-- exceptions.py              # Custom exceptions
|
+-- utils/                         # Utility components
|   |-- logging.py                 # Logging setup
|   |-- system.py                  # System detection
|   |-- platform_manager.py        # Platform-specific operations
|   |-- resource_manager.py        # Resource management
|
+-- main.py                        # Main entry point
```

## Key Component Details

### 1. Core Components

```
+------------------+       +--------------------+        +------------------+
|                  |       |                    |        |                  |
| WorkflowState    |<----->| MessageBus         |<------>| DependencyContnr |
| - Immutable      |       | - Pub/sub system   |        | - Component      |
| - Audit trail    |       | - Async messaging  |        |   lifecycle      |
| - Evolution      |       | - History tracking |        | - Initialization |
+------------------+       +--------------------+        +------------------+
```

-   **WorkflowState**: Core state management using immutable patterns
-   **MessageBus**: Asynchronous message passing system between components
-   **DependencyContainer**: Manages component dependencies and lifecycle

### 2. Multi-Agent Components

The multi-agent system architecture is divided into specialized agents:

```
                        +------------------------+
                        |                        |
                        | CoordinatorAgent       |
                        | - Workflow orchestration|
                        | - Plan execution       |
                        |                        |
                        +------------------------+
                            ^       ^      ^
                            |       |      |
                    +-------+       |      +-------+
                    |               |              |
        +-----------v----+ +--------v------+ +-----v----------+
        |                | |               | |                |
        | KnowledgeAgent | | ScriptBuilder | | ExecutionAgent |
        |                | |               | |                |
        +----------------+ +---------------+ +----------------+
                 ^                                    |
                 |                                    v
                 |           +-----------------+      |
                 +-----------| ImprovementAgent|<-----+
                             +-----------------+
```

-   **CoordinatorAgent**: Manages workflow lifecycle and coordination between agents
-   **KnowledgeAgent**: Handles documentation retrieval and knowledge management
-   **ScriptBuilderAgent**: Generates and validates scripts based on knowledge
-   **ExecutionAgent**: Runs scripts and verifies results
-   **ImprovementAgent**: Analyzes failures and improves future executions

### 3. Integration Components

The integration system provides a pluggable architecture for different types of integrations:

```
+------------------+       +--------------------+
|                  |       |                    |
| IntegrationBase  |------>| IntegrationRegistry|
| - Base class for |       | - Dynamic discovery|
|   all integrations       | - Target mapping   |
|                  |       |                    |
+------------------+       +--------------------+
        ^                           |
        |                           v
+-------+------------+     +------------------+
|                    |     |                  |
| ConcreteIntegrations     | Integration      |
| - Specific plugins |     | Templates        |
| - YAML definitions |     | - Jinja templates|
+--------------------+     +------------------+
```

-   **IntegrationBase**: Abstract base class for all integrations
-   **IntegrationRegistry**: Auto-discovery and registration of integration plugins
-   **Integration Templates**: Jinja templates for script generation

### 4. Script Generation Components

```
+------------------+       +--------------------+       +------------------+
|                  |       |                    |       |                  |
| ScriptGenerator  |<----->| TemplateRenderer   |<----->| ScriptValidator  |
| - Template-based |       | - Jinja2 templating|       | - Security checks|
| - Dynamic        |       | - Variable         |       | - Syntax         |
|                  |       |   substitution     |       |   validation     |
+------------------+       +--------------------+       +------------------+
        ^                           ^
        |                           |
+-------+------------+     +--------+---------+
|                    |     |                  |
| DynamicGenerator   |     | TemplateLoader   |
| - Documentation    |     | - Find templates |
|   based generation |     | - Load from      |
|                    |     |   multiple paths |
+--------------------+     +------------------+
```

-   **ScriptGenerator**: Creates scripts from templates with variable substitution
-   **ScriptValidator**: Validates scripts for security and correctness
-   **DynamicGenerator**: Generates scripts based on documentation knowledge

### 5. Execution Components

```
+------------------+       +--------------------+       +------------------+
|                  |       |                    |       |                  |
| ScriptExecutor   |<----->| IsolationMethods   |<----->| ResourceManager  |
| - Runs scripts   |       | - Direct execution |       | - Docker isolation |
| - Monitors       |       |                    |       | - Resource       |
|   execution      |       |                    |       |   cleanup        |
+------------------+       +--------------------+       +------------------+
        ^                                                       ^
        |                                                       |
        v                                                       v
+------------------+                                   +------------------+
|                  |                                   |                  |
| RecoveryManager  |                                   | ResourceLimiter  |
| - Error handling |                                   | - Memory limits  |
| - Rollback       |                                   | - Concurrent     |
|   operations     |                                   |   execution      |
+------------------+                                   +------------------+
```

-   **ScriptExecutor**: Executes scripts with platform-specific methods
-   **IsolationMethods**: Isolation options for script execution
-   **ResourceManager**: Manages resources during execution
-   **RecoveryManager**: Handles rollback and recovery operations

For details on how data flows between these components, see the [Data Flow](data-flow-readme.md) documentation.