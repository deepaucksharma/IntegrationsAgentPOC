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
from ..scripting.dynamic import DynamicScriptGenerator
from ..verification.dynamic import DynamicVerificationBuilder
from ..knowledge.integration import DynamicIntegrationKnowledge
from ..strategy.installation import InstallationStrategyAgent
from ..rollback.recovery import RecoveryManager
from ..storage.history import ExecutionHistoryManager
from ..config.configuration import WorkflowConfiguration

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
    
    def __init__(self, config: Optional[WorkflowConfiguration] = None):
        self.config = config
        self.registry = ComponentRegistry()
        self._setup_dependencies()

    def _setup_dependencies(self) -> None:
        """Setup component dependency graph."""
        self.dependencies = {
            'platform_manager': set(),
            'resource_manager': set(),
            'history_manager': set(),
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

    def register(self, name: str, component: Any) -> None:
        """Register a component with the container."""
        self.registry.components[name] = component
        self.registry.initialized[name] = False

    def get(self, name: str) -> Any:
        """Get a component from the container."""
        if name not in self.registry.components:
            raise InitializationError(
                f"Component {name} not found in container",
                details={"available_components": list(self.registry.components.keys())}
            )
        return self.registry.components[name]

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
                await component.initialize()
            self.registry.initialized[name] = True
        except Exception as e:
            raise InitializationError(
                f"Failed to initialize component {name}: {str(e)}",
                details={"component": name, "error": str(e)}
            )

    def validate_initialization(self) -> None:
        """Validate that all components are properly initialized."""
        uninitialized = [
            name for name, initialized in self.registry.initialized.items()
            if not initialized
        ]
        if uninitialized:
            raise InitializationError(
                "Some components are not initialized",
                details={"uninitialized_components": uninitialized}
            ) 