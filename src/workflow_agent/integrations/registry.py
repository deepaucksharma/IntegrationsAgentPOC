# src/workflow_agent/integrations/registry.py
import logging
import importlib
import inspect
import pkgutil
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Set, Tuple
from .base import IntegrationBase
from ..core.state import WorkflowState
from ..config.configuration import ensure_workflow_config
from ..utils.system import get_system_context

logger = logging.getLogger(__name__)

class IntegrationMetadata(object):
    """Metadata for an integration."""
    
    def __init__(
        self,
        name: str,
        category: str,
        targets: List[str],
        description: str = "",
        version: str = "1.0.0",
        author: str = "",
        dependencies: List[str] = None,
        compatibility: Dict[str, List[str]] = None,
        parameters: Dict[str, Dict[str, Any]] = None,
        tags: List[str] = None
    ):
        """Initialize integration metadata."""
        self.name = name
        self.category = category
        self.targets = targets
        self.description = description
        self.version = version
        self.author = author
        self.dependencies = dependencies or []
        self.compatibility = compatibility or {}
        self.parameters = parameters or {}
        self.tags = tags or []
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntegrationMetadata':
        """Create metadata from dictionary."""
        return cls(
            name=data.get("name", ""),
            category=data.get("category", "custom"),
            targets=data.get("targets", []),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            dependencies=data.get("dependencies", []),
            compatibility=data.get("compatibility", {}),
            parameters=data.get("parameters", {}),
            tags=data.get("tags", [])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "targets": self.targets,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "dependencies": self.dependencies,
            "compatibility": self.compatibility,
            "parameters": self.parameters,
            "tags": self.tags
        }
    
    def __repr__(self) -> str:
        """String representation of metadata."""
        return f"<IntegrationMetadata name={self.name} category={self.category} targets={len(self.targets)} tags={self.tags}>"

class IntegrationRegistry:
    """Enhanced registry for integration handlers with metadata support."""
    
    _integrations: Dict[str, Type[IntegrationBase]] = {}
    _metadata: Dict[str, IntegrationMetadata] = {}
    _loaded_paths: Set[str] = set()
    _categories: Dict[str, List[str]] = {}
    _targets_map: Dict[str, List[str]] = {}
    
    @classmethod
    def register(cls, integration_class: Type[IntegrationBase], metadata: Optional[IntegrationMetadata] = None) -> None:
        """
        Register an integration handler with optional metadata.
        
        Args:
            integration_class: Class that implements IntegrationBase
            metadata: Optional metadata for the integration
        """
        name = integration_class.get_name()
        cls._integrations[name] = integration_class
        
        # Extract metadata from class if not provided
        if metadata is None:
            targets = integration_class.get_supported_targets()
            category = getattr(integration_class, "category", "custom")
            description = getattr(integration_class, "__doc__", "") or ""
            version = getattr(integration_class, "version", "1.0.0")
            
            metadata = IntegrationMetadata(
                name=name,
                category=category,
                targets=targets,
                description=description,
                version=version
            )
        
        # Store metadata
        cls._metadata[name] = metadata
        
        # Update category index
        if metadata.category not in cls._categories:
            cls._categories[metadata.category] = []
        cls._categories[metadata.category].append(name)
        
        # Update targets index
        for target in metadata.targets:
            if target not in cls._targets_map:
                cls._targets_map[target] = []
            cls._targets_map[target].append(name)
        
        logger.debug(f"Registered integration handler: {name} ({metadata.category}) for targets: {metadata.targets}")
    
    @classmethod
    def get_integration(cls, name: str) -> Optional[Type[IntegrationBase]]:
        """
        Get integration handler by name.
        
        Args:
            name: Name of the integration
            
        Returns:
            Integration class or None if not found
        """
        return cls._integrations.get(name.lower())
    
    @classmethod
    def get_metadata(cls, name: str) -> Optional[IntegrationMetadata]:
        """
        Get integration metadata by name.
        
        Args:
            name: Name of the integration
            
        Returns:
            Integration metadata or None if not found
        """
        return cls._metadata.get(name.lower())
    
    @classmethod
    def list_integrations(cls) -> List[str]:
        """
        Get list of available integrations.
        
        Returns:
            List of integration names
        """
        return list(cls._integrations.keys())
    
    @classmethod
    def get_integrations_by_category(cls, category: str) -> List[str]:
        """
        Get list of integrations in a category.
        
        Args:
            category: Category name
            
        Returns:
            List of integration names
        """
        return cls._categories.get(category, [])
    
    @classmethod
    def get_integrations_for_target(cls, target: str) -> List[str]:
        """
        Get list of integrations that support a target.
        
        Args:
            target: Target name
            
        Returns:
            List of integration names
        """
        return cls._targets_map.get(target, [])
    
    @classmethod
    def get_best_integration_for_target(cls, target: str, integration_type: Optional[str] = None) -> Optional[Tuple[str, IntegrationMetadata]]:
        """
        Get the best integration for a target.
        
        Args:
            target: Target name
            integration_type: Optional integration type preference
            
        Returns:
            Tuple of (integration name, metadata) or None if no match
        """
        # If integration type is specified and supports the target, use it
        if integration_type and integration_type in cls._integrations:
            metadata = cls._metadata.get(integration_type)
            if metadata and target in metadata.targets:
                return integration_type, metadata
        
        # Get all integrations that support the target
        integrations = cls.get_integrations_for_target(target)
        if not integrations:
            return None
        
        # Score each integration's suitability
        scored_integrations = []
        for name in integrations:
            metadata = cls._metadata.get(name)
            if not metadata:
                continue
            
            # Calculate a simple score (higher is better)
            score = 0
            
            # Exact match is best
            if target == name:
                score += 100
            
            # Prefer integrations with more specific target lists
            score += (10 - min(10, len(metadata.targets)))
            
            # Prefer integrations with more specific target lists
            if name == "workflow_agent":
                score += 5
            
            scored_integrations.append((score, name, metadata))
        
        # Return highest scored integration
        if scored_integrations:
            scored_integrations.sort(reverse=True)
            return scored_integrations[0][1], scored_integrations[0][2]
        
        return None
    
    @classmethod
    def has_target(cls, target: str) -> bool:
        """
        Check if any integration supports the target.
        
        Args:
            target: Target name
            
        Returns:
            True if supported, False otherwise
        """
        return target in cls._targets_map
    
    @classmethod
    def get_categories(cls) -> List[str]:
        """
        Get list of all integration categories.
        
        Returns:
            List of category names
        """
        return list(cls._categories.keys())
    
    @classmethod
    def get_all_targets(cls) -> List[str]:
        """
        Get list of all supported targets.
        
        Returns:
            List of target names
        """
        return list(cls._targets_map.keys())
    
    @classmethod
    def get_targets_by_category(cls, category: str) -> List[str]:
        """
        Get list of targets in a category.
        
        Args:
            category: Category name
            
        Returns:
            List of target names
        """
        targets = set()
        for integration in cls.get_integrations_by_category(category):
            metadata = cls._metadata.get(integration)
            if metadata:
                targets.update(metadata.targets)
        return list(targets)
    
    @classmethod
    def discover_integrations(cls, package_path: str = None) -> None:
        """
        Discover and register integration handlers from a package.
        
        Args:
            package_path: Path to package containing integration modules
        """
        # Skip if already loaded
        if package_path in cls._loaded_paths:
            return
        
        if package_path:
            logger.info(f"Discovering integrations in {package_path}")
            try:
                # First, look for metadata files
                metadata_files = []
                try:
                    metadata_dir = Path(package_path) / "metadata"
                    if metadata_dir.exists():
                        for path in metadata_dir.glob("**/*.{json,yaml,yml}"):
                            metadata_files.append(path)
                except Exception as e:
                    logger.error(f"Error scanning for metadata files: {e}")
                
                # Load metadata
                for path in metadata_files:
                    try:
                        with open(path, "r") as f:
                            if path.suffix.lower() in (".yaml", ".yml"):
                                data = yaml.safe_load(f)
                            else:
                                data = json.load(f)
                            
                            # Handle single or multiple metadata entries
                            if isinstance(data, list):
                                for item in data:
                                    metadata = IntegrationMetadata.from_dict(item)
                                    cls._metadata[metadata.name] = metadata
                            else:
                                metadata = IntegrationMetadata.from_dict(data)
                                cls._metadata[metadata.name] = metadata
                    except Exception as e:
                        logger.error(f"Error loading metadata from {path}: {e}")
                
                # Load module integrations
                for finder, name, is_pkg in pkgutil.iter_modules([package_path]):
                    try:
                        module = importlib.import_module(f"{package_path}.{name}")
                        for item_name in dir(module):
                            item = getattr(module, item_name)
                            if (inspect.isclass(item) and 
                                issubclass(item, IntegrationBase) and 
                                item is not IntegrationBase):
                                # Get metadata if previously loaded
                                integration_name = item.get_name()
                                metadata = cls._metadata.get(integration_name)
                                cls.register(item, metadata)
                    except Exception as e:
                        logger.error(f"Error loading integration module {name}: {e}")
                
                # Mark path as loaded
                cls._loaded_paths.add(package_path)
            except Exception as e:
                logger.error(f"Error discovering integrations in {package_path}: {e}")

class IntegrationHandler:
    """Enhanced main handler for all integrations."""
    
    def __init__(self):
        """Initialize the integration handler."""
        # Import handlers here to avoid circular imports
        from .handlers.infra_agent import InfraAgentIntegration
        from .handlers.aws import AwsIntegration
        
        # Register built-in integrations
        IntegrationRegistry.register(InfraAgentIntegration)
        IntegrationRegistry.register(AwsIntegration)
        
        # Discover external integrations
        config = ensure_workflow_config()
        for plugin_dir in config.plugin_dirs:
            IntegrationRegistry.discover_integrations(plugin_dir)
    
    async def handle_integration(self, state: WorkflowState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle integration request based on integration type and target.
        
        Args:
            state: Current workflow state
            config: Optional configuration
            
        Returns:
            Dict with updates to workflow state
        """
        integration_type = state.integration_type.lower()
        target_name = state.target_name
        
        # Get integration handler
        integration_class = IntegrationRegistry.get_integration(integration_type)
        
        # If no direct integration match, try to find best match for target
        if not integration_class:
            best_match = IntegrationRegistry.get_best_integration_for_target(target_name, integration_type)
            if best_match:
                integration_name, metadata = best_match
                integration_class = IntegrationRegistry.get_integration(integration_name)
                logger.info(f"Using {integration_name} integration for {target_name}")
                
                # Update state with category
                state.integration_category = metadata.category
        
        # If still no handler, use fallback
        if not integration_class:
            logger.warning(f"No integration handler found for {integration_type}/{target_name}, using fallback")
            return {
                "script": f"""#!/usr/bin/env bash
set -e
echo "Handling generic integration for {state.target_name} using {state.integration_type}"
""",
                "source": "fallback_handler"
            }
        
        try:
            integration = integration_class()
            result = await integration.handle(state, config)
            
            # Add default system context if not provided
            if "system_context" not in result:
                result["system_context"] = get_system_context()
                
            return result
        except Exception as e:
            logger.error(f"Error handling {integration_type} integration: {e}")
            return {"error": f"Integration handler error: {str(e)}"}
    
    async def get_integration_info(self, integration_name: str = None, category: str = None, target: str = None) -> Dict[str, Any]:
        """
        Get information about integrations.
        
        Args:
            integration_name: Optional integration name
            category: Optional category
            target: Optional target
            
        Returns:
            Dictionary with integration information
        """
        if integration_name:
            # Get specific integration
            metadata = IntegrationRegistry.get_metadata(integration_name)
            if not metadata:
                return {"error": f"Integration {integration_name} not found"}
            
            return {"integration": metadata.to_dict()}
        
        elif category:
            # Get integrations in category
            integrations = IntegrationRegistry.get_integrations_by_category(category)
            
            return {
                "category": category,
                "integrations": [
                    IntegrationRegistry.get_metadata(name).to_dict() 
                    for name in integrations 
                    if IntegrationRegistry.get_metadata(name)
                ]
            }
        
        elif target:
            # Get integrations for target
            integrations = IntegrationRegistry.get_integrations_for_target(target)
            
            return {
                "target": target,
                "integrations": [
                    IntegrationRegistry.get_metadata(name).to_dict() 
                    for name in integrations 
                    if IntegrationRegistry.get_metadata(name)
                ]
            }
        
        else:
            # Get all categories and counts
            categories = IntegrationRegistry.get_categories()
            targets_count = len(IntegrationRegistry.get_all_targets())
            
            return {
                "categories": categories,
                "total_integrations": len(IntegrationRegistry.list_integrations()),
                "total_targets": targets_count
            }