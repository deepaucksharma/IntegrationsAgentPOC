"""Dependency injection container for workflow agent."""
import logging
from typing import Dict, Any, Optional, Type, TypeVar
from dataclasses import dataclass, field

from ..error.exceptions import InitializationError
from ..utils.platform_manager import PlatformManager
from ..utils.resource_manager import ResourceManager
from ..execution.executor import ScriptExecutor
from ..scripting.generator import ScriptGenerator
from ..scripting.validator import ScriptValidator
from ..scripting.dynamic_generator import DynamicScriptGenerator
from ..verification.dynamic import DynamicVerificationBuilder
from ..knowledge.integration import DynamicIntegrationKnowledge
from ..strategy.installation import InstallationStrategyAgent
from ..rollback.recovery import RecoveryManager
from ..storage.history import ExecutionHistoryManager
from ..config.configuration import WorkflowConfiguration
from ..integrations.manager import IntegrationManager

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class ComponentRegistry:
    """Registry for workflow agent components."""
    components: Dict[str, Any] = field(default_factory=dict)
    initialized: Dict[str, bool] = field(default_factory=dict)
    dependencies: Dict[str, set] = field(default_factory=dict)

class DependencyContainer:
    """Container for managing component dependencies and lifecycle."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._components = {}
        self._initialized = False
        self.registry = ComponentRegistry()
        self._setup_dependencies()

    def _setup_dependencies(self) -> None:
        """Setup component dependency graph."""
        self.dependencies = {
            'platform_manager': set(),
            'resource_manager': set(),
            'history_manager': set(),
            'integration_manager': set(),
            'script_executor': {'platform_manager', 'resource_manager'},
            'script_generator': {'history_manager'},
            'script_validator': set(),
            'dynamic_script_generator': set(),
            'verification_builder': set(),
            'integration_knowledge': set(),
            'installation_strategy': set(),
            'recovery_manager': {'history_manager'}
        }

    async def initialize(self) -> None:
        """Initialize all components in dependency order."""
        try:
            # Register core components
            self.register('platform_manager', PlatformManager())
            self.register('resource_manager', ResourceManager())
            self.register('history_manager', ExecutionHistoryManager())
            
            # Register integration manager
            if self.config and hasattr(self.config, 'plugin_dirs'):
                self.register('integration_manager', IntegrationManager(self.config.plugin_dirs))
            
            # Register execution components
            self.register('script_executor', ScriptExecutor(
                platform_manager=self.get('platform_manager'),
                resource_manager=self.get('resource_manager')
            ))
            
            # Register script handling components
            self.register('script_generator', ScriptGenerator(
                history_manager=self.get('history_manager')
            ))
            self.register('script_validator', ScriptValidator())
            self.register('dynamic_script_generator', DynamicScriptGenerator())
            
            # Register other components
            self.register('verification_builder', DynamicVerificationBuilder())
            self.register('integration_knowledge', DynamicIntegrationKnowledge())
            self.register('installation_strategy', InstallationStrategyAgent())
            self.register('recovery_manager', RecoveryManager(
                history_manager=self.get('history_manager')
            ))
            
            # Initialize components in dependency order
            for component_name in self._get_initialization_order():
                await self._initialize_component(component_name)
                
            self._initialized = True
            logger.info("Container initialization complete")
                
        except Exception as e:
            logger.error(f"Failed to initialize container: {e}")
            raise InitializationError(
                f"Container initialization failed: {str(e)}",
                details={"error": str(e)}
            )

    async def cleanup(self) -> None:
        """Clean up all components in reverse dependency order."""
        cleanup_order = list(reversed(self._get_initialization_order()))
        for component_name in cleanup_order:
            component = self.registry.components.get(component_name)
            if component and hasattr(component, 'cleanup'):
                try:
                    await component.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up component {component_name}: {e}")

        self.registry.components.clear()
        self._initialized = False
        logger.info("Container cleanup complete")

    def register(self, name: str, component: Any) -> None:
        """Register a component with the container."""
        self._components[name] = component
        logger.debug(f"Registered component: {name}")
        self.registry.components[name] = component
        self.registry.initialized[name] = False

    def get(self, name: str) -> Optional[Any]:
        """Get a registered component."""
        if not self._initialized:
            raise InitializationError("Container not initialized")
            
        component = self._components.get(name)
        if not component:
            raise InitializationError(f"Component {name} not found in container")
            
        return component

    def _get_initialization_order(self) -> list[str]:
        """Get component initialization order based on dependencies."""
        visited = set()
        order = []
        
        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            for dep in self.dependencies.get(name, set()):
                visit(dep)
            order.append(name)
        
        for name in self.dependencies:
            visit(name)
        return order

    async def _initialize_component(self, name: str) -> None:
        """Initialize a single component."""
        if self.registry.initialized.get(name):
            return
            
        component = self.registry.components.get(name)
        if not component:
            raise InitializationError(
                f"Component {name} not found during initialization",
                details={"component": name}
            )
            
        try:
            if hasattr(component, 'initialize'):
                logger.debug(f"Initializing component: {name}")
                await component.initialize()
            self.registry.initialized[name] = True
        except Exception as e:
            raise InitializationError(
                f"Failed to initialize component {name}: {str(e)}",
                details={"component": name, "error": str(e)}
            )

    def validate_initialization(self) -> None:
        """Validate container initialization."""
        if not self._initialized:
            raise InitializationError("Container not initialized")
            
        # Check required components
        required_components = [
            'integration_manager',
            'integration_registry',
            'recovery_manager',
            'script_generator',
            'storage_manager',
            'verification_manager',
            'documentation_handler'
        ]
        
        missing = [name for name in required_components if name not in self._components]
        if missing:
            raise InitializationError(f"Missing required components: {', '.join(missing)}") 