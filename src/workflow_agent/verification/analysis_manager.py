"""
Consolidated verification analysis module for LLM-based result analysis.
"""
import logging
import json
from typing import Dict, Any, List, Optional

from ..llm.service import LLMService

logger = logging.getLogger(__name__)

class VerificationAnalysisManager:
    """
    Provides consolidated analysis capabilities for all verification types.
    This centralizes the LLM-based analysis functionality that was previously
    duplicated across multiple methods in the VerificationManager.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize the analysis manager.
        
        Args:
            llm_service: LLM service for generating analysis
        """
        self.llm_service = llm_service or LLMService()
    
    async def analyze_verification_results(
        self, 
        passed_steps: List[Dict[str, Any]], 
        failed_steps: List[Dict[str, Any]], 
        total_steps: int,
        context: Dict[str, Any],
        analysis_type: str
    ) -> Dict[str, Any]:
        """
        Unified method to analyze verification results for any verification type.
        
        Args:
            passed_steps: Steps that passed verification
            failed_steps: Steps that failed verification
            total_steps: Total number of verification steps
            context: Context information about the integration
            analysis_type: Type of analysis to perform:
                - "verification": Standard verification analysis
                - "clean_verification": System clean state verification
                - "uninstall_verification": Uninstallation verification
                - "diagnostic": Diagnostic analysis
                
        Returns:
            Analysis results as a dictionary
        """
        # Calculate success metrics
        success_rate = len(passed_steps) / total_steps if total_steps > 0 else 0
        critical_failures = [step for step in failed_steps if step.get("required", True)]
        
        # Get the analysis purpose based on type
        verification_purposes = {
            "verification": "integration installation verification",
            "clean_verification": "system clean state verification after rollback",
            "uninstall_verification": "integration uninstallation verification",
            "diagnostic": "diagnostic analysis of failing components"
        }
        
        purpose = verification_purposes.get(analysis_type, "verification")
        
        # Prepare base prompt for all verification types
        base_prompt = f"""
        Analyze the results of {purpose} for a New Relic {context.get('integration_type')} integration.
        
        Verification summary:
        - Total steps: {total_steps}
        - Passed steps: {len(passed_steps)}
        - Failed steps: {len(failed_steps)}
        - Success rate: {success_rate:.2%}
        - Critical failures: {len(critical_failures)}
        
        Integration details:
        - Type: {context.get('integration_type')}
        - Target name: {context.get('target_name')}
        
        Passed steps:
        {json.dumps(passed_steps, indent=2)[:2000]}  # Limit for token reasons
        
        Failed steps:
        {json.dumps(failed_steps, indent=2)[:2000]}  # Limit for token reasons
        """
        
        # Add analysis-specific fields based on type
        output_schema = self._get_analysis_schema(analysis_type)
        
        # Complete the prompt
        prompt = base_prompt + "\nBased on these verification results, analyze:\n"
        prompt += "1. Is the " + purpose.split()[0] + " successful overall?\n"
        prompt += "2. What are the key issues, if any?\n"
        prompt += "3. How critical are the failed steps?\n"
        prompt += "4. What might be causing the failures?\n"
        prompt += "5. What next steps would you recommend?\n\n"
        prompt += f"Format your response as a JSON object with these keys:\n{output_schema}"
        
        try:
            # Generate analysis using LLM
            analysis = await self.llm_service.generate_json(
                prompt=prompt,
                system_prompt=f"You are an expert in analyzing {purpose} results and providing actionable insights.",
                temperature=0.2
            )
            
            return analysis
            
        except Exception as e:
            logger.warning(f"Error generating verification analysis: {e}")
            return self._generate_fallback_analysis(analysis_type, critical_failures, failed_steps)
    
    def _get_analysis_schema(self, analysis_type: str) -> str:
        """
        Get the schema for the analysis based on its type.
        
        Args:
            analysis_type: Type of analysis
            
        Returns:
            Schema description
        """
        schemas = {
            "verification": """
            - verification_successful: Boolean indicating if verification is successful overall
            - critical_issues: Boolean indicating if there are any critical issues
            - issues: Array of identified issues
            - impact: Description of the impact of any issues
            - recommendations: Array of recommended actions
            - reasoning: Explanation of your assessment
            """,
            
            "clean_verification": """
            - system_clean: Boolean indicating if the system is clean
            - remaining_artifacts: Array of any remaining artifacts
            - impact: Description of the impact of any remaining artifacts
            - recommendations: Array of recommended cleanup actions
            - reasoning: Explanation of your assessment
            """,
            
            "uninstall_verification": """
            - uninstall_successful: Boolean indicating if uninstallation was successful
            - critical_issues: Boolean indicating if there are critical issues
            - remaining_components: Array of remaining components
            - impact: Description of the impact of any remaining components
            - recommendations: Array of recommended cleanup actions
            - reasoning: Explanation of your assessment
            """,
            
            "diagnostic": """
            - findings: Array of key findings from the diagnostics
            - possible_issues: Array of possible root causes
            - recommendations: Array of recommended actions to resolve the issues
            - severity: Assessment of how severe the issues are
            """
        }
        
        return schemas.get(analysis_type, schemas["verification"])
    
    def _generate_fallback_analysis(
        self, 
        analysis_type: str, 
        critical_failures: List[Dict[str, Any]], 
        failed_steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a fallback analysis when LLM generation fails.
        
        Args:
            analysis_type: Type of analysis
            critical_failures: List of critical failed steps
            failed_steps: List of all failed steps
            
        Returns:
            Basic analysis results
        """
        # Basic analysis based on verification type
        if analysis_type == "verification":
            return {
                "verification_successful": len(critical_failures) == 0,
                "critical_issues": len(critical_failures) > 0,
                "issues": [step.get("error", "Unknown error") for step in failed_steps],
                "impact": "Unknown impact",
                "recommendations": ["Investigate failed steps manually"],
                "reasoning": "Basic analysis due to LLM error"
            }
        elif analysis_type == "clean_verification":
            return {
                "system_clean": len(failed_steps) == 0,
                "remaining_artifacts": [step.get("name", "Unknown") for step in failed_steps],
                "impact": "Potential system artifacts remaining",
                "recommendations": ["Manually clean up remaining artifacts"],
                "reasoning": "Basic analysis due to LLM error"
            }
        elif analysis_type == "uninstall_verification":
            return {
                "uninstall_successful": len(critical_failures) == 0,
                "critical_issues": len(critical_failures) > 0,
                "remaining_components": [step.get("name", "Unknown") for step in failed_steps],
                "impact": "Potential integration components remaining",
                "recommendations": ["Manually remove remaining components"],
                "reasoning": "Basic analysis due to LLM error"
            }
        elif analysis_type == "diagnostic":
            return {
                "findings": [step.get("error", "Unknown error") for step in failed_steps],
                "possible_issues": ["Unknown issue"],
                "recommendations": ["Manual investigation required"],
                "severity": "Unknown"
            }
        else:
            return {
                "success": len(critical_failures) == 0,
                "issues": [step.get("error", "Unknown error") for step in failed_steps],
                "reasoning": "Basic analysis due to LLM error"
            }
