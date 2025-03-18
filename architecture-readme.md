# Architecture Overview

The Workflow Agent framework follows a modular, message-driven architecture designed for extensibility and robustness.

## Navigation

-   [Overview](overview-readme.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Component Hierarchy](component-hierarchy-readme.md)
-   [Data Flow](data-flow-readme.md)
-   [Developer Setup & Troubleshooting](developer-readme.md)

## System Architecture Diagram

```
+--------------------------------------------------------------------------------------------------------+
|                                         WORKFLOW AGENT SYSTEM                                           |
+--------------------------------------------------------------------------------------------------------+
|                                                                                                        |
|  +--------------------+     +----------------------+     +--------------------+     +-----------------+ |
|  |                    |     |                      |     |                    |     |                 | |
|  |  User Interface    |---->|  Workflow Agent      |---->|  Multi-Agent       |---->|  Integration    | |
|  |  (CLI/API)         |     |  (Main Controller)   |     |  System            |     |  Registry       | |
|  |                    |     |                      |     |                    |     |                 | |
|  +--------------------+     +----------------------+     +--------------------+     +-----------------+ |
|                                       |                        ^  |                         ^          |
|                                       |                        |  |                         |          |
|                                       v                        |  v                         |          |
|  +--------------------+     +----------------------+     +--------------------+     +-----------------+ |
|  |                    |     |                      |     |                    |     |                 | |
|  |  Configuration     |---->|  Dependency          |---->|  Script Generator  |---->|  Documentation  | |
|  |  Management        |     |  Container           |     |  & Validator       |     |  Parser         | |
|  |                    |     |                      |     |                    |     |                 | |
|  +--------------------+     +----------------------+     +--------------------+     +-----------------+ |
|                                       |                           |                          |         |
|                                       |                           |                          |         |
|                                       v                           v                          v         |
|  +--------------------+     +----------------------+     +--------------------+     +-----------------+ |
|  |                    |     |                      |     |                    |     |                 | |
|  |  Execution         |<----|  Recovery Manager    |<----|  Knowledge Base    |<----|  Storage &      | |
|  |  Engine            |     |  (Rollback)          |     |  & Manager         |     |  History        | |
|  |                    |     |                      |     |                    |     |                 | |
|  +--------------------+     +----------------------+     +--------------------+     +-----------------+ |
|                                                                                                        |
+--------------------------------------------------------------------------------------------------------+
```

## Core Design Principles

### 1. Separation of Concerns

Each component has a specific role:

-   **Workflow Agent (Main)**: Entry point and orchestration
-   **Multi-Agent System**: Specialized agents for different tasks
-   **Integration Registry**: Plugin system for integrations
-   **Knowledge Management**: Documentation-based decision making
-   **Script Generation**: Platform-specific script creation
-   **Execution Engine**: Safe execution of generated scripts

### 2. Message-Driven Architecture

Components communicate through a publish-subscribe pattern using the MessageBus:

-   Decoupled components that can evolve independently
-   Asynchronous processing for better resource utilization
-   Easy to extend with new agents or components

### 3. Immutable State Management

The WorkflowState is designed as an immutable object:

-   State transitions create new instances with modifications
-   Complete audit trail of state changes
-   Thread-safe operation without locks

### 4. Dynamic Discovery

Components like integrations are discovered dynamically:

-   Plugin-based architecture for extensibility
-   No hardcoded dependencies
-   Self-registration through base classes

## Technical Stack

-   **Python 3.8+**: Core programming language
-   **Pydantic**: Data validation and settings management
-   **AsyncIO**: Asynchronous programming model
-   **Jinja2**: Template-based script generation
-   **SQLite**: Local data persistence
-   **Docker**: Optional isolation for execution

## System Boundaries

```
                                        +-----------------------+
                                        |                       |
                                        |  External Systems     |
                                        |  - Documentation Sites|
                                        |  - Package Managers   |
                                        |  - Target Systems     |
                                        |                       |
                                        +-----------+-----------+
                                                    |
                                                    v
+------------------+    +-----------------+    +----+-------------+
|                  |    |                 |    |                  |
|  User/Admin      +--->+  Workflow Agent +--->+  Target System   |
|  (CLI/API)       |    |  Framework      |    |  (for execution) |
|                  |    |                 |    |                  |
+------------------+    +-----------------+    +------------------+
```

## Key Interfaces

1.  **CLI/API Interface**: User interaction through command line or API
2.  **Integration Interface**: Standardized plugin system for adding new integrations
3.  **Documentation Interface**: Connection to external documentation sources
4.  **Execution Interface**: Abstraction for script execution in different environments

For more details on the multi-agent system architecture, see the [LLM & Agent System](llm-agents-readme.md) documentation.