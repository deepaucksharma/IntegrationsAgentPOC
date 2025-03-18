# Data Flow

This document details how data flows through the Workflow Agent system during execution, including command processing, state transitions, and message passing between components.

## Navigation

-   [Overview](overview-readme.md)
-   [Architecture Overview](architecture-readme.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Component Hierarchy](component-hierarchy-readme.md)
-   [Developer Setup & Troubleshooting](developer-readme.md)

## Primary Data Flow Diagram

```
                                               +---------------+
                                               |               |
                                 Command       | User/CLI/API  |
                                 Parameters    |               |
                                               +-------+-------+
                                                       |
                                                       v
+-------------------------+                    +-------+-------+
|                         |    Workflow        |               |
| Configuration System    +-------------------->  WorkflowAgent|
| - Config files          |    Configuration   |   (Main)      |
| - Environment variables |                    |               |
+-------------------------+                    +-------+-------+
                                                       |
                                                       |
                                                       v
+-------------------------+                    +-------+-------+          +---------------+
|                         |    Knowledge       |               |          |               |
| Knowledge Base          +-------------------->  CoordinatorAg|  State   | Storage       |
| - Documentation         |    Enhancement     |   (Controller)|--------->| - History     |
| - Integration info      |                    |               |          | - Audit trail |
+-------------------------+                    +-------+-------+          +---------------+
                                                       |
                                                       | Messages
                                                       v
                          +-------------------------------------------------------+
                          |                                                       |
                          |                    Message Bus                        |
                          |                                                       |
                          +---+-------------------+-------------------+---+-------+
                              |                   |                   |   |
                              |                   |                   |   |
           +------------------v--+      +---------v-------+     +----v---v--------+
           |                     |      |                 |     |                 |
           | Knowledge Agent     |      | Script Builder  |     | Execution Agent |
           |                     |      |                 |     |                 |
           +---------------------+      +-----------------+     +-----------------+
                      |                          |                       |
                      |  Enhanced               |                       |
                      |  Knowledge              |                       |
                      v                          v                       v
         +------------+------+       +----------+---------+     +-------+-------+
         |                   |       |                    |     |               |
         | Documentation     |       | Script Generator   |     | Executor      |
         | Parser            |       | + Validator        |     |               |
         +-------------------+       +--------------------+     +-------+-------+
                                                                        |
                                                                        v
                                                               +--------+--------+
                                                               |                 |
                                                               | Target System   |
                                                               | (Script Execution)
                                                               +-----------------+
```

## Workflow State Transitions

The WorkflowState object evolves through transitions as it progresses through the workflow:

```
             +-------------+
             | Initial     |
             | State       |
             +------+------+
                    |
                    v
     +-------------++--------------+
     |                             |
     |  Knowledge Enhancement      |
     |  - Add documentation        |
     |  - Platform info            |
     +-------------+--------------+
                   |
                   v
     +-------------+--------------+
     |                             |
     |  Strategy Selection         |
     |  - Select best method       |
     |  - Add scoring data         |
     +-------------+--------------+
                   |
                   v
     +-------------+--------------+
     |                             |
     |  Script Generation          |
     |  - Add script               |
     |  - Add template info        |
     +-------------+--------------+
                   |
                   v
     +-------------+--------------+
     |                             |
     |  Script Execution           |
     |  - Add output data          |
     |  - Add metrics              |
     |  - Add changes made         |
     +-------------+--------------+
                   |
                   v
     +-------------+--------------+
     |                             |
     |  Verification               |
     |  - Add verification result  |
     |  - Add warnings             |
     +-------------+--------------+
                   |
                   v
             +-----+------+
             | Final      |
             | State      |
             +------------+
```

## Key Data Structures

### 1. WorkflowState

The immutable state object contains all workflow information:

```
+------------------------------------------------------------+
|                     WorkflowState                           |
+------------------------------------------------------------+
| - action: str (install, remove, verify)                     |
| - target_name: str (integration target)                     |
| - integration_type: str (type of integration)               |
| - parameters: Dict[str, Any] (user-supplied params)         |
| - template_data: Dict[str, Any] (documentation knowledge)   |
| - system_context: Dict[str, Any] (platform information)     |
| - script: Optional[str] (generated script)                  |
| - template_key: Optional[str] (template identifier)         |
| - changes: List[Change] (changes during execution)          |
| - output: Optional[OutputData] (execution result)           |
| - metrics: Optional[ExecutionMetrics] (performance metrics) |
| - warnings: List[str] (non-fatal issues)                    |
| - error: Optional[str] (error message if failed)            |
+------------------------------------------------------------+
```

### 2. Message Format

Messages passed between agents follow this structure:

```
+-----------------------------------------------------------+
|                        Message                             |
+-----------------------------------------------------------+
| - workflow_id: str (unique workflow identifier)            |
| - state: Dict[str, Any] (serialized workflow state)        |
| - status: str (in_progress, success, failed)               |
| - stage: str (current workflow stage)                      |
| - config: Optional[Dict[str, Any]] (configuration)         |
| - additional_data: Dict[str, Any] (contextual information) |
+-----------------------------------------------------------+
```

## Message Topics

The system uses a publish-subscribe pattern with the following primary topics:

```
+-------------------+----------------------------------------+
| Topic             | Description                            |
+-------------------+----------------------------------------+
| retrieve_knowledge| Knowledge retrieval request            |
| knowledge_retrieved| Knowledge retrieval completed         |
| generate_script   | Script generation request              |
| script_generated  | Script generation completed            |
| validate_script   | Script validation request              |
| script_validated  | Script validation completed            |
| execute_script    | Script execution request               |
| execution_complete| Script execution completed             |
| verify_result     | Verification request                   |
| verification_complete| Verification completed              |
| analyze_failure   | Failure analysis request               |
| improvement_generated| Improvement suggestion completed    |
| error             | Error notification                     |
+-------------------+----------------------------------------+
```

## Data Flow Examples

### 1. Installation Workflow Data Flow

```
1. Initial Request:
   CLI/API -> WorkflowAgent -> CoordinatorAgent
   Data: {action: "install", target_name: "monitoring_agent", parameters: {...}}

2. Knowledge Retrieval:
   CoordinatorAgent -> KnowledgeAgent -> DocumentationParser
   Data: Integration type, target name, platform context

3. Knowledge Enhancement:
   DocumentationParser -> KnowledgeAgent -> CoordinatorAgent
   Data: Documentation knowledge, recommended approaches

4. Strategy Selection:
   CoordinatorAgent -> InstallationStrategy -> CoordinatorAgent
   Data: Available methods, scoring, selected approach

5. Script Generation:
   CoordinatorAgent -> ScriptBuilder -> ScriptGenerator
   Data: Template selection, variable substitution

6. Script Validation:
   ScriptGenerator -> ScriptValidator -> ScriptBuilder
   Data: Generated script, validation results

7. Script Execution:
   CoordinatorAgent -> ExecutionAgent -> ScriptExecutor
   Data: Validated script, execution context

8. Result Verification:
   ExecutionAgent -> Verifier -> ExecutionAgent
   Data: Execution output, verification criteria

9. Final Result:
   ExecutionAgent -> CoordinatorAgent -> CLI/API
   Data: Execution result, status, metrics
```

### 2. Failure Recovery Data Flow

```
1. Execution Failure:
   ScriptExecutor -> ExecutionAgent -> CoordinatorAgent
   Data: Error details, execution output

2. Failure Analysis:
   CoordinatorAgent -> ImprovementAgent
   Data: Error details, workflow state

3. Rollback Initiation: ## File: data-flow-readme.md (continued)
```markdown
3. Rollback Initiation:
   CoordinatorAgent -> RecoveryManager
   Data: Workflow state, changes to revert

4. Rollback Execution:
   RecoveryManager -> ScriptExecutor
   Data: Generated rollback script

5. Improvement Analysis:
   ImprovementAgent -> KnowledgeBase
   Data: Root cause analysis, suggested improvements

6. Result Notification:
   CoordinatorAgent -> CLI/API
   Data: Error information, rollback status
```

## State Evolution Examples

The following examples illustrate how state evolves during workflows:

### Installation Workflow State Evolution

```
1. Initial State:
   {
     "action": "install",
     "target_name": "monitoring_agent",
     "integration_type": "infra_agent",
     "parameters": {
       "license_key": "abc123",
       "host": "localhost"
     },
     "system_context": {
       "platform": {"system": "linux", "distribution": "ubuntu"}
     }
   }

2. Knowledge Enhanced State:
   {
     ... (previous state) ...,
     "template_data": {
       "docs": { ... documentation data ... },
       "platform_specific": { ... filtered data ... }
     }
   }

3. Strategy Selected State:
   {
     ... (previous state) ...,
     "selected_method": { ... method details ... },
     "method_scores": { ... scoring details ... }
   }

4. Script Generated State:
   {
     ... (previous state) ...,
     "script": "#!/bin/bash\n...",
     "template_key": "install/monitoring_agent.sh.j2"
   }

5. Execution Complete State:
   {
     ... (previous state) ...,
     "output": {
       "stdout": "...",
       "stderr": "...",
       "exit_code": 0
     },
     "changes": [
       {"type": "create", "target": "/opt/monitoring", ...},
       {"type": "config", "target": "config.yaml", ...}
     ],
     "metrics": {
       "duration": 2.5,
       "start_time": "...",
       "end_time": "..."
     }
   }

6. Verification Complete State:
   {
     ... (previous state) ...,
     "verification_result": true,
     "warnings": []
   }
```

For a more detailed understanding of how to set up the system and troubleshoot issues, see the [Developer Setup & Troubleshooting](developer-readme.md) guide.