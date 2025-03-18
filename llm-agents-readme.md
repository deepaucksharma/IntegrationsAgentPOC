# LLM & Agent System

The Workflow Agent framework utilizes a multi-agent system to coordinate different aspects of workflow execution.

## Navigation

-   [Overview](overview-readme.md)
-   [Architecture Overview](architecture-readme.md)
-   [Component Hierarchy](component-hierarchy-readme.md)
-   [Data Flow](data-flow-readme.md)
-   [Developer Setup & Troubleshooting](developer-readme.md)

## Agent System Architecture

```
+--------------------------------------------------------------+
|                      MULTI-AGENT SYSTEM                      |
+--------------------------------------------------------------+
|                                                              |
|  +-------------------+         +------------------------+    |
|  |                   |         |                        |    |
|  | Coordinator Agent |<------->| Message Bus            |    |
|  | (Orchestrator)    |         | (Communication Hub)    |    |
|  |                   |         |                        |    |
|  +-------------------+         +------------------------+    |
|          |                                ^                  |
|          |                                |                  |
|          v                                |                  |
|  +-------------------+         +------------------------+    |
|  |                   |         |                        |    |
|  | Knowledge Agent   |<------->| Script Builder Agent   |    |
|  | (Documentation)   |         | (Script Generation)    |    |
|  |                   |         |                        |    |
|  +-------------------+         +------------------------+    |
|          |                                ^                  |
|          |                                |                  |
|          v                                v                  |
|  +-------------------+         +------------------------+    |
|  |                   |         |                        |    |
|  | Execution Agent   |<------->| Improvement Agent      |    |
|  | (Script Runner)   |         | (Self-Improvement)     |    |
|  |                   |         |                        |    |
|  +-------------------+         +------------------------+    |
|                                                              |
+--------------------------------------------------------------+
```

## Agent Responsibilities

### 1. Coordinator Agent

Acts as the central orchestrator for the entire workflow:

-   Manages workflow lifecycle (start, monitor, completion)
-   Creates and maintains workflow plans
-   Schedules agent activities in the correct sequence
-   Handles the overall success/failure of workflow execution
-   Maintains state throughout the workflow

```
                  +--------------------+
                  |                    |
  start_workflow  |                    |  wait_for_completion
+---------------->+ Coordinator Agent  +<---------------------+
                  |                    |
                  |                    |
                  +--------------------+
                    |       |        ^
            publish |       | publish|
                    v       v        |
          +-------------+   +-------------+   +-------------+
          |             |   |             |   |             |
          | Knowledge   |   | Script      |   | Execution   |
          | Agent       |   | Builder     |   | Agent       |
          |             |   |             |   |             |
          +-------------+   +-------------+   +-------------+
```

### 2. Knowledge Agent

Manages documentation and knowledge retrieval:

-   Parses integration documentation from various sources
-   Extracts structured knowledge (prerequisites, steps, verification)
-   Filters information based on platform compatibility
-   Responds to knowledge queries from other agents
-   Indexes and manages the knowledge base

### 3. Script Builder Agent

Handles script generation and validation:

-   Generates scripts from templates and documentation knowledge
-   Validates scripts for security and correctness
-   Applies platform-specific optimizations
-   Ensures proper error handling in scripts
-   Handles variable substitution for customization

### 4. Execution Agent

Responsible for script execution and verification:

-   Executes scripts in appropriate environment (direct or isolated)
-   Monitors execution for timeouts and errors
-   Handles resource management during execution
-   Performs verification checks after execution
-   Manages cleanup of temporary resources

### 5. Improvement Agent

Focused on analyzing failures and improving future executions:

-   Analyzes workflow failures to determine root causes
-   Generates improvements to scripts and templates
-   Records successful patterns for future reference
-   Updates the knowledge base with learned information
-   Suggests optimizations for future workflows

## AI-Driven Components

The framework incorporates several AI-driven components:

### 1. Documentation Parser

Uses NLP techniques to extract structured information from documentation:

```
+-----------------+     +------------------+     +----------------+
|                 |     |                  |     |                |
| Raw             |---->| NLP Processing   |---->| Structured     |
| Documentation   |     | & Entity         |     | Knowledge      |
|                 |     | Extraction       |     |                |
+-----------------+     +------------------+     +----------------+
```

### 2. Strategy Selection

Evaluates and selects the optimal installation strategy:

```
+------------------+
| Installation     |
| Methods          |
+-------+----------+
        |
        v
+-------+----------+     +----------------+     +----------------+
|                  |     |                |     |                |
| Scoring System   |---->| Method Ranking |---->| Selected       |
| - Compatibility  |     |                |     | Strategy       |
| - Complexity     |     |                |     |                |
+------------------+     +----------------+     +----------------+
```

### 3. Failure Analysis

Analyzes execution failures to improve future workflows:

```
+----------------+     +------------------+     +----------------+
|                |     |                  |     |                |
| Execution      |---->| Root Cause       |---->| Script         |
| Failure        |     | Analysis         |---->| Improvements   |
|                |     |                  |     |                |
+----------------+     +------------------+     +----------------+
                               |
                               v
                       +------------------+
                       |                  |
                       | Knowledge Base   |
                       | Updates          |
                       |                  |
                       +------------------+
```

## Message-Based Communication

Agents communicate through a message bus using a publish-subscribe pattern:

```
+-----------------+                       +-----------------+
|                 |     publish           |                 |
| Source Agent    +---------------------->+ Message Bus     |
|                 |     (topic, payload)  |                 |
+-----------------+                       +--------+--------+
                                                   |
                                                   |
                                                   |
                                                   |
+-------------------+                    +---------v--------+
|                   |     callback       |                  |
| Subscriber Agent  +<-------------------+ Message          |
|                   |     (payload)      | Distribution     |
+-------------------+                    +------------------+
```

For more details on how these agents interact with the overall system components, see the [Component Hierarchy](component-hierarchy-readme.md) documentation.