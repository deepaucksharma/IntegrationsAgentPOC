# Data Flow

This document details how data flows through the enhanced Workflow Agent system during execution, including command processing, state transitions, checkpoint management, and message passing between components.

## Navigation

-   [Overview](README.md)
-   [Architecture Overview](architecture-readme.md)
-   [LLM & Agent System](llm-agents-readme.md)
-   [Component Hierarchy](component-hierarchy-readme.md)
-   [Developer Setup & Troubleshooting](developer-readme.md)
-   [Recent Fixes & Improvements](FIXED.md)

## Enhanced Primary Data Flow Diagram

```
                                               +---------------+
                                               |               |
                                 Command       | User/CLI/API  |
                                 Parameters    |               |
                                               +-------+-------+
                                                       |
                                                       v
+-------------------------+                    +-------+-------+
|                         |    Enhanced        |               |
| Configuration System    +-------------------->  WorkflowAgent|
| - Config files          |    Configuration   |   (Main)      |
| - Environment variables |    with validation |               |
+-------------------------+                    +-------+-------+
                                                       |
                                                       | Create Checkpoint
                                                       v
+-------------------------+                    +-------+-------+          +---------------+
|                         |    Knowledge       |               |          |               |
| Knowledge Base          +-------------------->  CoordinatorAg|  State   | Storage       |
| - Documentation         |    Enhancement     |   (Controller)|--------->| - History     |
| - Integration info      |                    |               |          | - Audit trail |
+-------------------------+                    +-------+-------+          | - Checkpoints |
                                                       |                  +---------------+
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
           |                     |      |                 |      |                |
           | Knowledge Agent     |      | Script Builder  |      | Execution Agent|
           |                     |      |                 |      |                |
           +---------------------+      +-----------------+      +----------------+
                      |                          |                        |
                      |  Enhanced               |                        |
                      |  Knowledge              |                        |
                      v                          v                        v
         +------------+------+       +----------+---------+     +--------+--------+
         |                   |       |                    |     |                 |
         | Documentation     |       | Enhanced Script    |     | Enhanced        |
         | Parser            |       | Generator+Validator|     | Executor        |
         +-------------------+       +--------------------+     +--------+--------+
                                                                         |
                                                                         v
                                                               +---------+---------+
                                                               |                   |
                                                               | Target System     |
                                                               | (Script Execution)|
                                                               +---------+---------+
                                                                         |
                                                                         | Error?
                                                                         v
                                                               +---------+---------+
                                                               |                   |
                                                               | Recovery Manager  |
                                                               | - Tiered rollback |
                                                               | - Verification    |
                                                               +-------------------+
```

## Enhanced Workflow State Transitions with Checkpoints

The WorkflowState object evolves through transitions with comprehensive checkpointing:

```
              +----------------+
              | Initial State  |
              +-------+--------+
                      |
                      v
              +-------+--------+
              | Initialization |
              | Checkpoint     |
              +-------+--------+
                      |
                      v
     +----------------+-----------------+
     |                                  |
     | Enhanced Input Validation        |
     | - Parameter validation           |
     | - Integration validation         |
     | - Environment validation         |
     +----------------+-----------------+
                      |
                      v
              +-------+--------+
              | Validation     |
              | Checkpoint     |
              +-------+--------+
                      |
                      v
     +----------------+-----------------+
     |                                  |
     | Enhanced Knowledge Enhancement   |
     | - Add documentation              |
     | - Platform info                  |
     | - Security considerations        |
     +----------------+-----------------+
                      |
                      v
              +-------+--------+
              | Generation     |
              | Checkpoint     |
              +-------+--------+
                      |
                      v
     +----------------+-----------------+
     |                                  |
     | Enhanced Script Generation       |
     | - Add script                     |
     | - Add template info              |
     | - Multiple security validations  |
     +----------------+-----------------+
                      |
                      v
              +-------+--------+
              | Execution      |
              | Checkpoint     |
              +-------+--------+
                      |
                      v
     +----------------+-----------------+
     |                                  |
     | Enhanced Script Execution        |
     | - Add output data                |
     | - Add metrics                    |
     | - Robust change tracking         |
     +----------------+-----------------+
                      |
                      v
              +-------+--------+
              | Verification   |
              | Checkpoint     |
              +-------+--------+
                      |
                      v
     +----------------+-----------------+
     |                                  |
     | Enhanced Verification            |
     | - Add verification result        |
     | - System state validation        |
     | - Add warnings                   |
     +----------------+-----------------+
                      |
                      v
              +-------+--------+
              | Completion     |
              | Checkpoint     |
              +-------+--------+
                      |
                      v
              +-------+--------+
              | Final State    |
              +----------------+
```

## Enhanced State Structure

### 1. Enhanced WorkflowState

The immutable state object with enhanced recovery capabilities:

```
+------------------------------------------------------------+
|                     Enhanced WorkflowState                  |
+------------------------------------------------------------+
| - action: str (install, remove, verify)                     |
| - target_name: str (integration target)                     |
| - integration_type: str (type of integration)               |
| - parameters: Dict[str, Any] (user-supplied params)         |
| - template_data: Dict[str, Any] (documentation knowledge)   |
| - system_context: Dict[str, Any] (platform information)     |
| - script: Optional[str] (generated script)                  |
| - template_key: Optional[str] (template identifier)         |
|                                                             |
| - changes: List[Change] (enhanced change tracking)          |
| - output: Optional[OutputData] (execution result)           |
| - metrics: Optional[ExecutionMetrics] (performance metrics) |
| - warnings: List[str] (non-fatal issues)                    |
| - error: Optional[str] (error message if failed)            |
|                                                             |
| # Enhanced recovery features                                |
| - current_stage: WorkflowStage (current workflow stage)     |
| - checkpoints: Dict[str, Any] (stage checkpoints)           |
| - retry_count: int (number of retries)                      |
| - backup_files: List[str] (backup file tracking)            |
| - verification_results: Dict[str, Any] (verification data)  |
| - rollback_script: Optional[str] (generated rollback script)|
| - recovery_strategy: Optional[str] (recovery approach)      |
+------------------------------------------------------------+
```

### 2. Enhanced Change Tracking

The enhanced Change object with improved rollback support:

```
+------------------------------------------------------------+
|                      Enhanced Change                        |
+------------------------------------------------------------+
| - type: str (change type)                                   |
| - target: str (affected target)                             |
| - revertible: bool (can be reverted)                        |
| - revert_command: Optional[str] (command to revert)         |
| - backup_file: Optional[str] (backup file location)         |
| - timestamp: datetime (when change was made)                |
| - change_id: UUID (unique identifier)                       |
| - metadata: Dict[str, Any] (additional data)                |
|                                                             |
| # New verification fields                                   |
| - verified: bool (whether change was verified)              |
| - rollback_attempted: bool (rollback was attempted)         |
| - rollback_success: Optional[bool] (rollback succeeded)     |
+------------------------------------------------------------+
```

### 3. Enhanced Message Format

Messages passed between agents with improved error handling:

```
+-----------------------------------------------------------+
|                    Enhanced Message                        |
+-----------------------------------------------------------+
| - workflow_id: str (unique workflow identifier)            |
| - state: Dict[str, Any] (serialized workflow state)        |
| - status: str (in_progress, success, failed, retrying)     |
| - stage: str (current workflow stage)                      |
| - config: Optional[Dict[str, Any]] (configuration)         |
| - checkpoint_id: Optional[str] (checkpoint identifier)     |
| - retry_count: int (number of retries)                     |
| - additional_data: Dict[str, Any] (contextual information) |
+-----------------------------------------------------------+
```

## Enhanced Message Topics

The system uses a publish-subscribe pattern with the following enhanced topics:

```
+-------------------+----------------------------------------+
| Topic             | Description                            |
+-------------------+----------------------------------------+
| workflow_start    | Workflow initiation with validation    |
| workflow_checkpoint| Checkpoint created                    |
| retrieve_knowledge| Knowledge retrieval request            |
| knowledge_retrieved| Knowledge retrieval completed         |
| generate_script   | Script generation request              |
| script_generated  | Script generation completed            |
| validate_script   | Enhanced script validation request     |
| script_validated  | Script validation completed            |
| execute_script    | Script execution request               |
| execution_complete| Script execution completed             |
| verify_result     | Enhanced verification request          |
| verification_complete| Verification completed              |
| analyze_failure   | Failure analysis request               |
| improvement_generated| Improvement suggestion completed    |
| error             | Error notification                     |
| recovery_start    | Recovery initiation                    |
| recovery_complete | Recovery completion                    |
| rollback_start    | Rollback initiation                    |
| rollback_complete | Rollback completion                    |
+-------------------+----------------------------------------+
```

## Enhanced Data Flow Examples

### 1. Enhanced Installation Workflow Data Flow

```
1. Initial Request:
   CLI/API -> WorkflowAgent -> CoordinatorAgent
   Data: {action: "install", target_name: "monitoring_agent", parameters: {...}}

2. Input Validation:
   WorkflowAgent -> Validate all inputs
   Data: Parameters, environment, integrations

3. Knowledge Retrieval:
   CoordinatorAgent -> KnowledgeAgent -> DocumentationParser
   Data: Integration type, target name, platform context
   Checkpoint: Create Initialization checkpoint

4. Knowledge Enhancement:
   DocumentationParser -> KnowledgeAgent -> CoordinatorAgent
   Data: Documentation knowledge, recommended approaches
   Checkpoint: Create Knowledge checkpoint

5. Strategy Selection:
   CoordinatorAgent -> InstallationStrategy -> CoordinatorAgent
   Data: Available methods, scoring, selected approach

6. Enhanced Script Generation:
   CoordinatorAgent -> ScriptBuilder -> ScriptGenerator
   Data: Template selection, variable substitution
   Checkpoint: Create Generation checkpoint

7. Enhanced Script Validation:
   ScriptGenerator -> ScriptValidator -> ScriptBuilder
   Data: Generated script, multiple validation results (static analysis, security patterns)

8. Enhanced Script Execution:
   CoordinatorAgent -> ExecutionAgent -> ScriptExecutor
   Data: Validated script, execution context
   Checkpoint: Create Execution checkpoint

9. Enhanced Change Tracking:
   ScriptExecutor -> Process change markers -> WorkflowState
   Data: Detailed changes with backup files and metadata

10. Enhanced Result Verification:
    ExecutionAgent -> Verifier -> ExecutionAgent
    Data: Execution output, verification criteria, system state checks
    Checkpoint: Create Verification checkpoint

11. Final Result:
    ExecutionAgent -> CoordinatorAgent -> CLI/API
    Data: Execution result, status, metrics
    Checkpoint: Create Completion checkpoint
```

### 2. Enhanced Failure Recovery Data Flow

```
1. Execution Failure:
   ScriptExecutor -> ExecutionAgent -> CoordinatorAgent
   Data: Error details, execution output

2. Recovery Planning:
   CoordinatorAgent -> RecoveryManager
   Data: Error type, retry eligibility, last checkpoint

3. Retry Decision:
   RecoveryManager -> Decision point (can retry?)
   If yes: Return to appropriate checkpoint
   If no: Proceed to rollback

4. Enhanced Rollback Initiation:
   CoordinatorAgent -> RecoveryManager
   Data: Workflow state, changes to revert

5. Tiered Rollback Strategy:
   RecoveryManager -> Choose strategy (full, staged, individual)
   Data: Change types, severity, system context

6. Enhanced Rollback Execution:
   RecoveryManager -> ScriptExecutor
   Data: Generated rollback script with error handling

7. Rollback Verification:
   RecoveryManager -> VerificationManager
   Data: System state after rollback

8. Enhanced Result Notification:
   CoordinatorAgent -> CLI/API
   Data: Error information, recovery outcome, partial success details
```

## Retry and Recovery Flow

The new retry and recovery flow allows for partial workflow recovery:

```
             +---------------+
             | Error Occurs  |
             +-------+-------+
                     |
                     v
             +-------+-------+
             | Is Error      |
             | Retryable?    |
             +-------+-------+
             /               \
            /                 \
           / Yes               \ No
          v                     v
  +-------+-------+     +-------+-------+
  | Find Last     |     | Start          |
  | Checkpoint    |     | Rollback       |
  +-------+-------+     +-------+-------+
          |                     |
          v                     v
  +-------+-------+     +-------+-------+
  | Retry From     |     | Try Full      |
  | Checkpoint     |     | Rollback      |
  +-------+-------+     +-------+-------+
      Success?               Success?
          /  \                  /  \
         /    \                /    \
 Yes    /      \    No  Yes   /      \    No
       v        v            v        v
  +-------+ +---+---+   +----+--+ +---+---+
  | Resume | | Retry  |   | Done  | | Try    |
  | Flow   | | Limit? |   |       | | Staged |
  +-------+ +---+---+   +----+--+ +---+---+
                 | No           Success?
                 v                /  \
            +----+---+           /    \
            | Start  |   Yes    /      \    No
            | Staged |<--------+        +----->+------+
            | Rollback                        | Try   |
            +--------+                        | Indiv.|
                                              +---+---+
```

For a more detailed understanding of how to set up the system and troubleshoot issues, see the [Developer Setup & Troubleshooting](developer-readme.md) guide.