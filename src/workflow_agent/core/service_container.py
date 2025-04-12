"""
Enhanced service container with lifecycle management and auto-wiring capabilities.
This implementation extends and enhances the base DependencyContainer with
richer service lifecycle management and dependency tracking.
"""
import logging
import inspect
from enum import Enum
from typing import Dict, Any, Optional, Type, TypeVar, Generic, cast, List, Set, Callable
import asyncio
from dataclasses import dataclass
import time

from ..error.exceptions import InitializationError, ValidationError
from ..error.handler import handle_safely
from .container import Provider, SingletonProvider, FactoryProvider, InstanceProvider, DependencyContainer

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ServiceLifecycle(str, Enum):
    """Service lifecycle states."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DISPOSING = "disposing"
    DISPOSED = "disposed"

class ServiceMetadata:
    """Metadata about a service."""
    
    def __init__(
        self, 
        service_type: Type, 
        name: str, 
        tags: List[str] = None,
        dependencies: List[str] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.UNINITIALIZED
    ):
        self.service_type = service_type
        self.name = name
        self.tags = tags or []
        self.dependencies = dependencies or []
        self.lifecycle = lifecycle
        self.created_at = time.time()
        self.initialized_at: Optional[float] = None
        self.last_used_at: Optional[float] = None
        self.disposed_at: Optional[float] = None
        
    def mark_initializing(self) -> None:
        """Mark service as initializing."""
        self.lifecycle = ServiceLifecycle.INITIALIZING
        
    def mark_active(self) -> None:
        """Mark service as active."""
        self.lifecycle = ServiceLifecycle.ACTIVE
        self.initialized_at = time.time()
        
    def mark_used(self) -> None:
        """Mark service as used."""
        self.last_used_at = time.time()
        
    def mark_disposing(self) -> None:
        """Mark service as disposing."""
        self.lifecycle = ServiceLifecycle.DISPOSING
        
    def mark_disposed(self) -> None:
        """Mark service as disposed."""
        self.lifecycle = ServiceLifecycle.DISPOSED
        self.disposed_at = time.time()
        
    def is_active(self) -> bool:
        """Check if service is active."""
        return self.lifecycle == ServiceLifecycle.ACTIVE
        
    def is_disposed(self) -> bool:
        """Check if service is disposed."""
        return self.lifecycle in [ServiceLifecycle.DISPOSING, ServiceLifecycle.DISPOSED]

class TrackedProvider(Provider, Generic[T]):
    """Provider that tracks service lifecycle."""
    
    def __init__(self, provider: Provider[T], metadata: ServiceMetadata):
        """
        Initialize the tracked provider.
        
        Args:
            provider: Underlying provider
            metadata: Service metadata
        """
        self.provider = provider
        self.metadata = metadata
        
    def get(self) -> T:
        """
        Get the service, tracking usage.
        
        Returns:
            Service instance
        """
        self.metadata.mark_used()
        if self.metadata.is_disposed():
            raise InitializationError(f"Service {self.metadata.name} has been disposed")
        return self.provider.get()
        
class ServiceDependencyType(str, Enum):
    """Types of service dependencies."""
    REQUIRED = "required"
    OPTIONAL = "optional"
    TAGGED = "tagged"
    FACTORY = "factory"

@dataclass
class ServiceDependency:
    """Dependency information for a service."""
    name: str
    dependency_type: ServiceDependencyType = ServiceDependencyType.REQUIRED
    tag: Optional[str] = None
    
class ServiceContainer:
    """
    Enhanced service container with lifecycle management, auto-wiring, and dependency tracking.
    Extends the base DependencyContainer with richer features for service management.
    """
    
    def __init__(self):
        """Initialize the service container."""
        self.container = DependencyContainer()
        self.metadata: Dict[str, ServiceMetadata] = {}
        self.tag_registry: Dict[str, List[str]] = {}
        
    def register_service(
        self, 
        name: str, 
        service_type: Type[T], 
        provider_type: str = "singleton",
        instance: Optional[Any] = None,
        *args,
        tags: List[str] = None,
        **kwargs
    ) -> None:
        """
        Consolidated service registration method.
        
        Args:
            name: Service name
            service_type: Service type
            provider_type: Provider type (singleton, factory, instance)
            instance: Pre-created instance (for instance provider)
            tags: Optional list of tags for service discovery
            *args: Arguments for service initialization
            **kwargs: Keyword arguments for service initialization
        """
        # Extract dependencies from constructor (except for instance provider)
        dependencies = []
        if provider_type != "instance":
            dependencies = self._extract_dependencies(service_type)
        
        # Create metadata
        metadata = ServiceMetadata(
            service_type=service_type if provider_type != "instance" else type(instance),
            name=name,
            tags=tags or [],
            dependencies=[dep.name for dep in dependencies],
            lifecycle=ServiceLifecycle.ACTIVE if provider_type == "instance" else ServiceLifecycle.UNINITIALIZED
        )
        
        # Register provider with dependency container
        if provider_type == "singleton":
            self.container.register_singleton(name, service_type, *args, **kwargs)
        elif provider_type == "factory":
            self.container.register_factory(name, service_type, *args, **kwargs)
        elif provider_type == "instance":
            self.container.register_instance(name, instance)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        # Wrap with tracked provider
        provider = self.container.providers[name]
        self.container.providers[name] = TrackedProvider(provider, metadata)
        
        # Store metadata
        self.metadata[name] = metadata
        
        # Register tags
        for tag in metadata.tags:
            if tag not in self.tag_registry:
                self.tag_registry[tag] = []
            self.tag_registry[tag].append(name)
        
        # Mark instance provider as active since it's pre-initialized
        if provider_type == "instance":
            metadata.mark_active()
            
        logger.debug(f"Registered {provider_type} service: {name} ({metadata.service_type.__name__})")

    def register_singleton(self, name: str, service_type: Type[T], *args, tags: List[str] = None, **kwargs) -> None:
        """Register a singleton service (convenience method)."""
        self.register_service(name, service_type, "singleton", None, *args, tags=tags, **kwargs)
        
    def register_factory(self, name: str, service_type: Type[T], *args, tags: List[str] = None, **kwargs) -> None:
        """Register a factory service (convenience method)."""
        self.register_service(name, service_type, "factory", None, *args, tags=tags, **kwargs)
        
    def register_instance(self, name: str, instance: Any, tags: List[str] = None) -> None:
        """Register a pre-created instance (convenience method)."""
        self.register_service(name, type(instance), "instance", instance, tags=tags)
        
    def get(self, name: str) -> Any:
        """
        Get a service by name, tracking usage.
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            InitializationError: If service not found
        """
        result = self.container.get(name)
        
        # Update metadata if found
        if name in self.metadata:
            self.metadata[name].mark_used()
            
        return result
        
    def get_by_tag(self, tag: str) -> List[Any]:
        """
        Get all services with a specific tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of service instances
        """
        services = []
        
        if tag in self.tag_registry:
            for name in self.tag_registry[tag]:
                try:
                    services.append(self.get(name))
                except Exception as e:
                    logger.warning(f"Error getting service {name} with tag {tag}: {e}")
                    
        return services
        
    def has(self, name: str) -> bool:
        """
        Check if a service is registered.
        
        Args:
            name: Service name
            
        Returns:
            True if service is registered
        """
        return self.container.has(name)
        
    def register_alias(self, alias: str, target: str) -> None:
        """
        Register an alias for a service.
        
        Args:
            alias: Alias name
            target: Target service name
        """
        self.container.register_alias(alias, target)
        
    async def initialize_services(self, service_names: Optional[List[str]] = None) -> None:
        """
        Initialize services and their dependencies asynchronously.
        
        Args:
            service_names: Optional list of services to initialize
                           If None, initializes all services
                           
        Raises:
            InitializationError: If initialization fails
        """
        # If no services specified, initialize all
        if service_names is None:
            service_names = list(self.metadata.keys())
            
        # Track initialized services to avoid duplicates
        initialized = set()
        
        # Initialize in dependency order
        for name in service_names:
            await self._initialize_service_recursive(name, initialized, set())
            
        logger.info(f"Initialized {len(initialized)} services")
        
    async def _initialize_service_recursive(
        self, 
        name: str, 
        initialized: Set[str], 
        visiting: Set[str]
    ) -> None:
        """
        Initialize a service and its dependencies recursively.
        
        Args:
            name: Service name
            initialized: Set of already initialized services
            visiting: Set of services currently being initialized (for cycle detection)
            
        Raises:
            InitializationError: If initialization fails or circular dependency detected
        """
        # Skip if already initialized
        if name in initialized:
            return
            
        # Check for circular dependencies
        if name in visiting:
            raise InitializationError(f"Circular dependency detected: {visiting}")
            
        # Mark as visiting
        visiting.add(name)
        
        try:
            # Get metadata
            if name not in self.metadata:
                raise InitializationError(f"Service not found: {name}")
                
            metadata = self.metadata[name]
            
            # Initialize dependencies first
            for dep_name in metadata.dependencies:
                if dep_name not in initialized:
                    await self._initialize_service_recursive(dep_name, initialized, visiting)
                    
            # Get the service instance
            metadata.mark_initializing()
            instance = self.get(name)
            
            # Call initialize method if it exists
            if hasattr(instance, "initialize") and callable(instance.initialize):
                init_method = getattr(instance, "initialize")
                
                # Check if it's an async method
                if asyncio.iscoroutinefunction(init_method):
                    await init_method()
                else:
                    init_method()
                    
            # Mark as initialized
            metadata.mark_active()
            initialized.add(name)
            logger.debug(f"Initialized service: {name}")
            
        finally:
            # Remove from visiting set
            visiting.remove(name)
            
    async def dispose_services(self, service_names: Optional[List[str]] = None) -> None:
        """
        Dispose services in reverse dependency order.
        
        Args:
            service_names: Optional list of services to dispose
                           If None, disposes all services
        """
        # If no services specified, dispose all
        if service_names is None:
            service_names = list(self.metadata.keys())
            
        # Build a dependency graph for reverse traversal
        dependencies: Dict[str, List[str]] = {}
        for name, metadata in self.metadata.items():
            dependencies[name] = []
            
        for name, metadata in self.metadata.items():
            for dep_name in metadata.dependencies:
                if dep_name in dependencies:
                    dependencies[dep_name].append(name)
                    
        # Dispose in reverse dependency order
        disposed = set()
        
        for name in service_names:
            await self._dispose_service_recursive(name, dependencies, disposed)
            
        logger.info(f"Disposed {len(disposed)} services")
        
    async def _dispose_service_recursive(
        self, 
        name: str, 
        dependencies: Dict[str, List[str]], 
        disposed: Set[str]
    ) -> None:
        """
        Dispose a service and its dependents recursively.
        
        Args:
            name: Service name
            dependencies: Map of service to its dependents
            disposed: Set of already disposed services
        """
        # Skip if already disposed
        if name in disposed:
            return
            
        # Dispose dependents first
        if name in dependencies:
            for dep_name in dependencies[name]:
                await self._dispose_service_recursive(dep_name, dependencies, disposed)
                
        # Get metadata
        if name not in self.metadata:
            logger.warning(f"Service not found during disposal: {name}")
            return
            
        metadata = self.metadata[name]
        
        # Skip if not active
        if not metadata.is_active():
            logger.debug(f"Skipping disposal of inactive service: {name}")
            return
            
        # Mark as disposing
        metadata.mark_disposing()
        
        try:
            # Get the service instance
            instance = self.container.get(name)
            
            # Call cleanup method if it exists
            if hasattr(instance, "cleanup") and callable(instance.cleanup):
                cleanup_method = getattr(instance, "cleanup")
                
                # Check if it's an async method
                if asyncio.iscoroutinefunction(cleanup_method):
                    await cleanup_method()
                else:
                    cleanup_method()
                    
            # Mark as disposed
            metadata.mark_disposed()
            disposed.add(name)
            logger.debug(f"Disposed service: {name}")
            
        except Exception as e:
            logger.error(f"Error disposing service {name}: {e}")
            # Mark as disposed anyway
            metadata.mark_disposed()
            disposed.add(name)
            
    def get_service_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered services.
        
        Returns:
            List of service information dictionaries
        """
        services = []
        
        for name, metadata in self.metadata.items():
            services.append({
                "name": name,
                "type": metadata.service_type.__name__,
                "lifecycle": metadata.lifecycle,
                "tags": metadata.tags,
                "dependencies": metadata.dependencies,
                "created_at": metadata.created_at,
                "initialized_at": metadata.initialized_at,
                "last_used_at": metadata.last_used_at,
                "disposed_at": metadata.disposed_at
            })
            
        return services
        
    def _extract_dependencies(self, service_type: Type[T]) -> List[ServiceDependency]:
        """
        Extract dependencies from service constructor.
        
        Args:
            service_type: Service type
            
        Returns:
            List of service dependencies
        """
        dependencies = []
        
        try:
            # Get constructor parameters
            signature = inspect.signature(service_type.__init__)
            
            # Skip self parameter
            for name, param in list(signature.parameters.items())[1:]:
                # Extract annotation if available
                annotation = param.annotation
                
                # Skip if no annotation or not a class
                if annotation == inspect.Parameter.empty:
                    continue
                    
                # Create dependency info
                dependency = ServiceDependency(name=name)
                
                # Check for optional dependencies (default value)
                if param.default != inspect.Parameter.empty:
                    dependency.dependency_type = ServiceDependencyType.OPTIONAL
                    
                dependencies.append(dependency)
                
        except Exception as e:
            logger.warning(f"Error extracting dependencies from {service_type.__name__}: {e}")
            
        return dependencies
        
    @handle_safely
    def auto_wire(self, instance: Any) -> None:
        """
        Auto-wire dependencies for an existing instance.
        
        Args:
            instance: Instance to auto-wire
        """
        # Get class type
        instance_type = type(instance)
        
        # Get constructor signature
        signature = inspect.signature(instance_type.__init__)
        
        # Collect settable properties
        properties = {}
        
        # Check for non-initialized constructor parameters
        for name, param in list(signature.parameters.items())[1:]:  # Skip 'self'
            # Skip if already set
            if hasattr(instance, name) and getattr(instance, name) is not None:
                continue
                
            # Try to resolve from container
            if self.has(name):
                service = self.get(name)
                properties[name] = service
                
        # Set properties
        for name, value in properties.items():
            setattr(instance, name, value)
            
    def build_default_container(self, config) -> 'ServiceContainer':
        """
        Build a default container with standard services.
        
        Args:
            config: Application configuration
            
        Returns:
            Configured service container
        """
        # Create basic container
        self.container.build_default_container(config)
        
        # Copy over providers and initialize metadata
        for name, provider in self.container.providers.items():
            if name not in self.metadata:
                # Create basic metadata for existing services
                metadata = ServiceMetadata(
                    service_type=provider.__class__,
                    name=name,
                    tags=[],
                    lifecycle=ServiceLifecycle.UNINITIALIZED
                )
                
                # Add appropriate tags based on service name
                if name.endswith("_manager"):
                    metadata.tags.append("manager")
                if "template" in name:
                    metadata.tags.append("template")
                if name in ["template_registry", "template_pipeline", "template_manager"]:
                    metadata.tags.append("template_system")
                
                # Wrap provider
                self.container.providers[name] = TrackedProvider(provider, metadata)
                
                # Store metadata
                self.metadata[name] = metadata
                
        return self
