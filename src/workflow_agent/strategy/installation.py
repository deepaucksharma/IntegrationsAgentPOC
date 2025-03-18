import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class InstallationStrategyAgent:
    """Determines the best installation approach based on system context."""
    def __init__(self):
        self.scoring_weights = {
            "platform_match": 5.0,
            "complexity": 3.0,
            "prerequisites": 2.0,
            "reliability": 4.0
        }

    async def determine_best_approach(self, state: Any) -> Any:
        logger.info("Determining best installation approach")
        methods = state.template_data.get("platform_specific", {}).get("installation_methods", [])
        if not methods:
            methods = state.template_data.get("docs", {}).get("installation_methods", [])
        if not methods:
            raise Exception("No installation methods available")
        scored_methods = []
        for method in methods:
            score = self._calculate_compatibility_score(method, state)
            scored_methods.append((method, score))
            logger.debug(f"Method '{method.get('name', 'unknown')}' scored: {score}")
        scored_methods.sort(key=lambda x: x[1], reverse=True)
        best_method = scored_methods[0][0]
        state.template_data["selected_method"] = best_method
        state.template_data["method_scores"] = {m.get("name", "unknown"): s for m, s in scored_methods}
        logger.info(f"Selected installation method: {best_method.get('name', 'unknown')}")
        return state

    def _calculate_compatibility_score(self, method: Dict[str, Any], state: Any) -> float:
        score = 0.0
        platform_info = state.template_data.get("platform_info", {})
        platform_score = 1.0 if platform_info.get("system", "") in " ".join(method.get("platform_compatibility", [])).lower() else 0.0
        score += platform_score * self.scoring_weights["platform_match"]
        steps = method.get("steps", [])
        complexity_score = 1.0 / (1.0 + len(steps) * 0.1)
        score += complexity_score * self.scoring_weights["complexity"]
        prereqs = self._get_method_prerequisites(method, state)
        prereq_score = 1.0 / (1.0 + len(prereqs) * 0.2)
        score += prereq_score * self.scoring_weights["prerequisites"]
        reliability_score = self._calculate_reliability_score(method)
        score += reliability_score * self.scoring_weights["reliability"]
        return score

    def _get_method_prerequisites(self, method: Dict[str, Any], state: Any) -> List[str]:
        all_prereqs = state.template_data.get("platform_specific", {}).get("prerequisites", [])
        method_name = method.get("name", "").lower()
        return [p for p in all_prereqs if method_name in p.lower()]

    def _calculate_reliability_score(self, method: Dict[str, Any]) -> float:
        name = method.get("name", "").lower()
        if any(pm in name for pm in ["apt", "yum", "dnf", "msi"]):
            return 1.0
        if "docker" in name:
            return 0.8
        if "manual" in name:
            return 0.4
        if "script" in name:
            return 0.7
        return 0.5