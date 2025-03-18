import logging
from typing import Dict, Any, Optional
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config

logger = logging.getLogger(__name__)

class Verifier:
    async def verify_result(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if state.error:
            return {"error": f"Cannot verify: execution failed with error: {state.error}"}
        if not state.output:
            return {"error": "No output to verify."}
        workflow_config = ensure_workflow_config(config or {})
        if workflow_config.skip_verification:
            return {"status": "Verification skipped"}
        if state.output.exit_code != 0:
            return {"error": f"Verification failed: script exited with code {state.output.exit_code}"}
        stderr = state.output.stderr.lower()
        if "error" in stderr or "failed" in stderr:
            return {"error": f"Verification failed due to error in stderr: {stderr}"}
        return {"status": "Verification passed"}