"""Module for determining optimal installation strategies based on system context."""
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

class InstallationStrategyAgent:
    """Determines the best installation approach based on system context."""
    
    def __init__(self):
        """Initialize the strategy agent with scoring weights."""
        self.scoring_weights = {
            "platform_match": 5.0,  # High weight for platform compatibility
            "complexity": 3.0,      # Medium weight for installation complexity
            "prerequisites": 2.0,   # Lower weight for prerequisite requirements
            "reliability": 4.0      # High weight for method reliability
        }

    async def determine_best_approach(self, state: Any) -> Any:
        """Selects the optimal installation method.
        
        Args:
            state: Current workflow state with documentation data
            
        Returns:
            Updated state with selected installation method
            
        Raises:
            Exception: If no suitable installation method is found
        """
        try:
            logger.info("Determining best installation approach")
            
            # Get platform-specific installation methods
            methods = state.template_data.get("platform_specific", {}).get("installation_methods", [])
            
            if not methods:
                logger.warning("No platform-specific installation methods found, falling back to all methods")
                methods = state.template_data.get("docs", {}).get("installation_methods", [])
            
            if not methods:
                raise Exception("No installation methods available")
            
            # Score each method
            scored_methods = []
            for method in methods:
                score = self._calculate_compatibility_score(method, state)
                scored_methods.append((method, score))
                logger.debug(f"Method '{method.get('name', 'unknown')}' scored: {score}")
            
            # Sort by score and select the best method
            scored_methods.sort(key=lambda x: x[1], reverse=True)
            best_method = scored_methods[0][0]
            
            # Update state with selected method and scoring info
            state.template_data["selected_method"] = best_method
            state.template_data["method_scores"] = {
                method.get("name", "unknown"): score 
                for method, score in scored_methods
            }
            
            logger.info(f"Selected installation method: {best_method.get('name', 'unknown')}")
            return state
            
        except Exception as e:
            logger.error(f"Failed to determine installation approach: {e}")
            raise

    def _calculate_compatibility_score(self, method: Dict[str, Any], state: Any) -> float:
        """Calculates a compatibility score for an installation method.
        
        Args:
            method: Installation method dictionary
            state: Current workflow state
            
        Returns:
            Float score indicating method compatibility (higher is better)
        """
        score = 0.0
        platform_info = state.template_data.get("platform_info", {})
        
        # Platform compatibility score
        platform_score = self._calculate_platform_score(method, platform_info)
        score += platform_score * self.scoring_weights["platform_match"]
        
        # Complexity score (inverse of step count)
        steps = method.get("steps", [])
        complexity_score = 1.0 / (1.0 + len(steps) * 0.1)  # Normalize step count impact
        score += complexity_score * self.scoring_weights["complexity"]
        
        # Prerequisites score (inverse of prerequisite count)
        prereqs = self._get_method_prerequisites(method, state)
        prereq_score = 1.0 / (1.0 + len(prereqs) * 0.2)  # Normalize prerequisite count impact
        score += prereq_score * self.scoring_weights["prerequisites"]
        
        # Reliability score based on method type
        reliability_score = self._calculate_reliability_score(method)
        score += reliability_score * self.scoring_weights["reliability"]
        
        return score

    def _calculate_platform_score(self, method: Dict[str, Any], platform_info: Dict[str, str]) -> float:
        """Calculates platform compatibility score.
        
        Args:
            method: Installation method dictionary
            platform_info: Platform information dictionary
            
        Returns:
            Float score for platform compatibility (0.0 to 1.0)
        """
        platform_compat = method.get("platform_compatibility", [])
        
        # If no platform compatibility specified, assume moderate compatibility
        if not platform_compat:
            return 0.5
        
        # Perfect match for system
        if platform_info.get("system", "") in platform_compat:
            return 1.0
            
        # Distribution match for Linux
        if (platform_info.get("system") == "linux" and 
            platform_info.get("distribution", "") in platform_compat):
            return 0.9
            
        return 0.0

    def _get_method_prerequisites(self, method: Dict[str, Any], state: Any) -> List[str]:
        """Gets prerequisites specific to an installation method.
        
        Args:
            method: Installation method dictionary
            state: Current workflow state
            
        Returns:
            List of prerequisite strings
        """
        all_prereqs = state.template_data.get("platform_specific", {}).get("prerequisites", [])
        method_name = method.get("name", "").lower()
        
        # Filter prerequisites that mention this method
        return [
            prereq for prereq in all_prereqs 
            if method_name in prereq.lower()
        ]

    def _calculate_reliability_score(self, method: Dict[str, Any]) -> float:
        """Calculates reliability score based on method type.
        
        Args:
            method: Installation method dictionary
            
        Returns:
            Float score for reliability (0.0 to 1.0)
        """
        method_name = method.get("name", "").lower()
        
        # Prefer package manager installations
        if any(pm in method_name for pm in ["apt", "yum", "dnf", "pkg", "msi"]):
            return 1.0
            
        # Docker installations are reliable but may have overhead
        if "docker" in method_name:
            return 0.8
            
        # Manual installations are less reliable
        if "manual" in method_name:
            return 0.4
            
        # Script-based installations are moderately reliable
        if "script" in method_name:
            return 0.7
            
        # Default moderate reliability
        return 0.5 