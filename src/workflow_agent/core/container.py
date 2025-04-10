"""
Dependency container for managing component dependencies.
"""
import logging
from typing import Dict, Any, Optional, Type, TypeVar, Generic, cast
from dataclasses import dataclass

from ..error.exceptions import InitializationError
from ..utils.platform_manager import PlatformManager
from ..utils.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

T = TypeVar('T')

class Provider:
    """Interface for component provider."""
    def get(self) -> Any:
        """Get instance of component."""
        raise NotImplementedError("Provider must implement get()")

class SingletonProvider(Provider, Generic[T]):
    """Provider that creates a singleton instance."""
    
    def __init__(self, component_type: Type[T], *args, **kwargs):
        """
        Initialize with component type and arguments.
        
        Args:
            component_type: Class to instantiate
            *args: Arguments for initialization
            **kwargs: Keyword arguments for initialization
        """
        self.component_type = component_type
        self.args = args
        self.kwargs = kwargs
        self.instance: Optional[T] = None
        
    def get(self) -> T:
        """
        Get or create instance.
        
        Returns:
            Component instance
        """
        if self.instance is None:
            self.instance = self.component_type(*self.args, **self.kwargs)
        return self.instance

class FactoryProvider(Provider, Generic[T]):
    """Provider that creates a new instance each time."""
    
    def __init__(self, component_type: Type[T], *args, **kwargs):
        """
        Initialize with component type and arguments.
        
        Args:
            component_type: Class to instantiate
            *args: Arguments for initialization
            **kwargs: Keyword arguments for initialization
        """
        self.component_type = component_type
        self.args = args
        self.kwargs = kwargs
        
    def get(self) -> T:
        """
        Create and return new instance.
        
        Returns:
            Component instance
        """
        return self.component_type(*self.args, **self.kwargs)

class InstanceProvider(Provider, Generic[T]):
    """Provider that returns a pre-created instance."""
    
    def __init__(self, instance: T):
        """
        Initialize with instance.
        
        Args:
            instance: Pre-created component instance
        """
        self.instance = instance
        
    def get(self) -> T:
        """
        Return the instance.
        
        Returns:
            Component instance
        """
        return self.instance

class DependencyContainer:
    """
    Container for managing component dependencies with enhanced provider management.
    Supports singleton, factory, and instance providers.
    """
    
    def __init__(self):
        """Initialize container with empty providers dictionary."""
        self.providers: Dict[str, Provider] = {}
        self.aliases: Dict[str, str] = {}
        
    def register_singleton(self, name: str, component_type: Type[T], *args, **kwargs) -> None:
        """
        Register a singleton provider.
        
        Args:
            name: Component name
            component_type: Class to instantiate
            *args: Arguments for initialization
            **kwargs: Keyword arguments for initialization
        """
        self.providers[name] = SingletonProvider(component_type, *args, **kwargs)
        
    def register_factory(self, name: str, component_type: Type[T], *args, **kwargs) -> None:
        """
        Register a factory provider.
        
        Args:
            name: Component name
            component_type: Class to instantiate
            *args: Arguments for initialization
            **kwargs: Keyword arguments for initialization
        """
        self.providers[name] = FactoryProvider(component_type, *args, **kwargs)
        
    def register_instance(self, name: str, instance: T) -> None:
        """
        Register an instance provider.
        
        Args:
            name: Component name
            instance: Pre-created component instance
        """
        self.providers[name] = InstanceProvider(instance)
        
    def register_alias(self, alias: str, target: str) -> None:
        """
        Register an alias for a component.
        
        Args:
            alias: Alias name
            target: Target component name
        """
        if target not in self.providers and target not in self.aliases:
            raise InitializationError(f"Cannot alias to non-existent component: {target}")
        self.aliases[alias] = target
        
    def get(self, name: str) -> Any:
        """
        Get a component by name.
        
        Args:
            name: Component name
            
        Returns:
            Component instance
            
        Raises:
            InitializationError: If component not found
        """
        # Resolve aliases
        resolved_name = name
        visited_aliases = set()
        
        while resolved_name in self.aliases:
            if resolved_name in visited_aliases:
                raise InitializationError(f"Circular alias detected: {visited_aliases}")
            visited_aliases.add(resolved_name)
            resolved_name = self.aliases[resolved_name]
            
        if resolved_name not in self.providers:
            raise InitializationError(f"Component not found: {name} (resolved to {resolved_name})")
            
        return self.providers[resolved_name].get()
        
    def has(self, name: str) -> bool:
        """
        Check if a component is registered.
        
        Args:
            name: Component name
            
        Returns:
            True if component is registered, False otherwise
        """
        # Resolve aliases
        resolved_name = name
        visited_aliases = set()
        
        while resolved_name in self.aliases:
            if resolved_name in visited_aliases:
                return False  # Circular alias
            visited_aliases.add(resolved_name)
            resolved_name = self.aliases[resolved_name]
            
        return resolved_name in self.providers
        
    def get_typed(self, name: str, expected_type: Type[T]) -> T:
        """
        Get a component with type checking.
        
        Args:
            name: Component name
            expected_type: Expected component type
            
        Returns:
            Component instance of expected type
            
        Raises:
            InitializationError: If component not found or wrong type
        """
        component = self.get(name)
        
        if not isinstance(component, expected_type):
            raise InitializationError(
                f"Component {name} is not of expected type {expected_type.__name__}, "
                f"got {type(component).__name__}"
            )
            
        return cast(expected_type, component)
        
    def build_default_container(self, config) -> 'DependencyContainer':
        """
        Build a default container with standard dependencies.
        
        Args:
            config: Application configuration
            
        Returns:
            Configured container
        """
        # Create resource and platform managers
        self.register_singleton("platform_manager", PlatformManager)
        self.register_singleton("resource_manager", ResourceManager, config)
        
        # Register the config
        self.register_instance("config", config)
        
        # Load additional components from modules
        self._load_execution_components(config)
        self._load_scripting_components(config)
        self._load_verification_components(config)
        self._load_knowledge_components(config)
        self._load_strategy_components(config)
        self._load_recovery_components(config)
        self._load_storage_components(config)
        self._load_integration_components(config)
        
        return self
    
    def _load_execution_components(self, config) -> None:
        """Load execution-related components."""
        from ..execution.executor import ScriptExecutor
        from ..execution.isolation import IsolationFactory
        
        self.register_singleton("script_executor", ScriptExecutor, config)
        self.register_singleton("isolation_factory", IsolationFactory)
        
    def _load_scripting_components(self, config) -> None:
        """Load scripting-related components."""
        from ..scripting.generator import ScriptGenerator
        from ..scripting.validator import ScriptValidator
        from ..scripting.dynamic_generator import DynamicScriptGenerator
        from ..templates import TemplateManager
        from ..templates.registry.template_registry import TemplateRegistry
        from ..templates.pipeline import create_default_pipeline
        from ..agent.script_agent import ScriptGenerationAgent
        
        # Set up template components
        template_manager = TemplateManager(config)
        self.register_instance("template_manager", template_manager)
        
        # Register template registry and pipeline 
        registry = TemplateRegistry(search_paths=[
            str(path) for path in template_manager.template_dirs.values() if path.exists()
        ])
        registry.scan_templates()  
        self.register_instance("template_registry", registry)
        
        # Create and register template pipeline
        pipeline = create_default_pipeline(
            search_paths=[str(path) for path in template_manager.template_dirs.values() if path.exists()],
            registry=registry
        )
        self.register_instance("template_pipeline", pipeline)
        
        # Register traditional script components
        self.register_singleton("script_generator", ScriptGenerator, config, template_manager)
        self.register_singleton("script_validator", ScriptValidator, config)
        self.register_singleton("dynamic_script_generator", DynamicScriptGenerator, config)
        
        # Register agent-based components
        self.register_singleton("script_generation_agent", ScriptGenerationAgent, template_manager)
        
    def _load_verification_components(self, config) -> None:
        """Load verification-related components."""
        from ..verification.dynamic import DynamicVerificationBuilder
        from ..verification.manager import VerificationManager
        from ..agent.verification_agent import VerificationAgent
        
        # Need template manager for VerificationManager
        template_manager = self.get("template_manager")
        
        # Register traditional verification components
        self.register_singleton("verification_manager", VerificationManager, config, template_manager)
        self.register_singleton("dynamic_verification_builder", DynamicVerificationBuilder, config)
        
        # Register agent-based components
        self.register_singleton("verification_agent", VerificationAgent)
        
    def _load_knowledge_components(self, config) -> None:
        """Load knowledge-related components."""
        from ..knowledge.integration import DynamicIntegrationKnowledge
        
        self.register_singleton("dynamic_integration_knowledge", DynamicIntegrationKnowledge)
        
    def _load_strategy_components(self, config) -> None:
        """Load strategy-related components."""
        from ..strategy.installation import InstallationStrategyAgent
        
        self.register_singleton("installation_strategy_agent", InstallationStrategyAgent)
        
    def _load_recovery_components(self, config) -> None:
        """Load recovery-related components."""
        from ..rollback.recovery import RecoveryManager
        
        self.register_singleton("recovery_manager", RecoveryManager, config)
        
    def _load_storage_components(self, config) -> None:
        """Load storage-related components."""
        from ..storage.history import ExecutionHistoryManager
        from .state_manager import StateManager
        
        # Register state manager with config-specified storage path
        storage_path = getattr(config, "state_storage_path", "workflow_states.db")
        self.register_singleton("state_manager", StateManager, storage_path)
        
        # Register execution history manager
        self.register_singleton("execution_history_manager", ExecutionHistoryManager, config)
        
    def _load_integration_components(self, config) -> None:
        """Load integration-related components."""
        from ..integrations.manager import IntegrationManager
        from ..integrations.registry import IntegrationRegistry
        
        registry = IntegrationRegistry()
        self.register_instance("integration_registry", registry)
        
        self.register_singleton("integration_manager", IntegrationManager, config, registry)
