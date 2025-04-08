# Component Hierarchy

This document outlines the hierarchical structure of the Workflow Agent framework's components and their relationships with enhanced security, state management, and recovery capabilities.

## Navigation

-   [Overview](README.md)
-   [Architecture Overview](architecture-readme.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Data Flow](data-flow-readme.md)
-   [Developer Setup & Troubleshooting](developer-readme.md)
-   [Recent Fixes & Improvements](FIXED.md)

## Component Tree

```
workflow_agent/
|
+-- core/                          # Core framework components
|   |-- state.py                   # Enhanced immutable state management with checkpointing
|   |-- message_bus.py             # Pub/sub communication
|   |-- container.py               # Dependency injection
|
+-- config/                        # Configuration management
|   |-- configuration.py           # Enhanced configuration validation with security checks
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
|   |-- validator.py               # Enhanced script validation with static analysis
|   |-- dynamic_generator.py       # Dynamic script creation
|
+-- execution/                     # Script execution
|   |-- executor.py                # Enhanced script execution with robust change tracking
|   |-- isolation.py               # Improved execution isolation methods
|
+-- storage/                       # Data persistence
|   |-- history.py                 # Execution history
|   |-- knowledge_base.py          # Knowledge storage
|
+-- strategy/                      # Decision strategies
|   |-- installation.py            # Installation strategy selection
|
+-- recovery/                      # Enhanced error recovery
|   |-- manager.py                 # Recovery management with multiple strategies
|
+-- rollback/                      # Rollback operations
|   |-- recovery.py                # Enhanced rollback with verification
|
+-- verification/                  # Result verification
|   |-- verifier.py                # Verification engine
|   |-- dynamic.py                 # Dynamic verification building
|   |-- manager.py                 # Manages verification with system state checks
|
+-- error/                         # Error handling
|   |-- exceptions.py              # Custom exceptions
|
+-- utils/                         # Utility components
|   |-- logging.py                 # Enhanced logging setup
|   |-- system.py                  # System detection
|   |-- platform_manager.py        # Platform-specific operations
|   |-- resource_manager.py        # Resource management
|
+-- main.py                        # Enhanced main entry point with workflow stages
```

## Key Component Details

### 1. Core Components - Enhanced State Management

```
+---------------------+       +-----------------------+        +------------------+
|                     |       |                       |        |                  |
| WorkflowState       |<----->| MessageBus            |<------>| DependencyContnr |
| - Immutable         |       | - Pub/sub system      |        | - Component      |
| - Checkpoint support|       | - Async messaging     |        |   lifecycle      |
| - Workflow stages   |       | - Enhanced tracking   |        | - Initialization |
+---------------------+       +-----------------------+        +------------------+
```

-   **WorkflowState**: Core state management with enhanced immutable patterns, checkpoint support, and workflow stages
-   **MessageBus**: Asynchronous message passing system between components with improved reliability
-   **DependencyContainer**: Manages component dependencies and lifecycle

### 2. Multi-Agent Components

The multi-agent system architecture is divided into specialized agents:

```
                        +---------------------------------+
                        |                                 |
                        | CoordinatorAgent                |
                        | - Enhanced workflow orchestration|
                        | - Retry and recovery management |
                        | - Checkpoint tracking           |
                        +---------------------------------+
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

-   **CoordinatorAgent**: Manages workflow lifecycle with enhanced error handling and recovery
-   **KnowledgeAgent**: Handles documentation retrieval and knowledge management
-   **ScriptBuilderAgent**: Generates and validates scripts with improved security checks
-   **ExecutionAgent**: Runs scripts with robust change tracking and verification
-   **ImprovementAgent**: Analyzes failures and improves future executions

### 3. Enhanced Script Validation and Execution

```
+------------------------+       +-------------------------+       +----------------------+
|                        |       |                         |       |                      |
| ScriptGenerator        |<----->| Enhanced ScriptValidator|<----->| Static Analysis      |
| - Template-based       |       | - Multiple validation   |       | - Shell script checks|
| - Dynamic generation   |       |   layers                |       | - PowerShell checks  |
| - Error handling       |       | - Security pattern      |       | - Python validation  |
|                        |       |   detection             |       |                      |
+------------------------+       +-------------------------+       +----------------------+
        ^                                     ^
        |                                     |
+-------+--------------------+     +----------+-----------+
|                            |     |                      |
| DynamicGenerator           |     | TemplateLoader       |
| - Documentation            |     | - Enhanced template  |
|   based generation         |     |   discovery          |
|                            |     |                      |
+----------------------------+     +----------------------+
```

-   **ScriptGenerator**: Creates scripts from templates with improved error handling
-   **ScriptValidator**: Enhanced validation with multiple layers of security and correctness checks
-   **Static Analysis**: Integration with tools like shellcheck for shell scripts

### 4. Enhanced Execution and Recovery Components

```
+------------------------+       +-------------------------+       +----------------------+
|                        |       |                         |       |                      |
| Enhanced ScriptExecutor|<----->| IsolationMethods        |<----->| ResourceManager      |
| - Robust change tracking       | - Direct execution      |       | - Docker isolation   |
| - Security validation  |       | - Docker isolation      |       | - Resource cleanup   |
| - Timeout handling     |       |                         |       |                      |
+------------------------+       +-------------------------+       +----------------------+
        ^                                                                   ^
        |                                                                   |
        v                                                                   v
+------------------------+                                       +---------------------+
|                        |                                       |                     |
| Enhanced RecoveryManager|                                      | ResourceLimiter     |
| - Multiple strategies  |                                       | - Memory limits     |
| - Tiered rollback      |                                       | - Concurrent        |
| - Verification         |                                       |   execution         |
+------------------------+                                       +---------------------+
```

-   **Enhanced ScriptExecutor**: Executes scripts with robust change tracking and security validation
-   **IsolationMethods**: Improved isolation options for script execution
-   **ResourceManager**: Better management of resources during execution
-   **Enhanced RecoveryManager**: Comprehensive recovery with multiple strategies and verification

### 5. Improved Verification Components

```
+------------------------+       +-------------------------+       +----------------------+
|                        |       |                         |       |                      |
| VerificationManager    |<----->| Verifier                |<----->| SystemStateChecker   |
| - Manages verification |       | - Verification engine   |       | - Checks system      |
| - Verification strategies      | - Result validation     |       |   integrity          |
| - Post-rollback checks |       |                         |       |                      |
+------------------------+       +-------------------------+       +----------------------+
        ^                                     ^
        |                                     |
+-------+--------------------+     +----------+-----------+
|                            |     |                      |
| DynamicVerificationBuilder |     | VerificationSteps    |
| - Generate verification    |     | - Predefined steps   |
|   steps                    |     | - Custom steps       |
|                            |     |                      |
+----------------------------+     +----------------------+
```

-   **VerificationManager**: Manages the verification process with enhanced system state checking
-   **Verifier**: Performs verification with improved result validation
-   **SystemStateChecker**: New component to verify system integrity after operations
-   **DynamicVerificationBuilder**: Generates verification steps based on operations

For details on how data flows between these components, see the [Data Flow](data-flow-readme.md) documentation.