import logging
from typing import Any, Dict, Optional, Type, TypeVar, Callable
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class ServiceDefinition:
    """Definition of a service in the DI container."""
    service_type: Type
    factory: Callable
    singleton: bool
    instance: Optional[Any] = None

class Container:
    """Dependency injection container."""
    
    def __init__(self):
        """Initialize the container."""
        self._services: Dict[str, ServiceDefinition] = {}
        self._factories: Dict[str, Callable] = {}
        
    def register(
        self,
        service_type: Type[T],
        factory: Optional[Callable] = None,
        singleton: bool = True
    ) -> None:
        """
        Register a service in the container.
        
        Args:
            service_type: Type of the service
            factory: Optional factory function
            singleton: Whether the service should be a singleton
        """
        service_name = service_type.__name__
        
        if factory is None:
            factory = service_type
            
        self._services[service_name] = ServiceDefinition(
            service_type=service_type,
            factory=factory,
            singleton=singleton
        )
        
    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable
    ) -> None:
        """
        Register a factory for a service.
        
        Args:
            service_type: Type of the service
            factory: Factory function
        """
        service_name = service_type.__name__
        self._factories[service_name] = factory
        
    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service from the container.
        
        Args:
            service_type: Type of the service to resolve
            
        Returns:
            Service instance
        """
        service_name = service_type.__name__
        
        # Check if service is registered
        if service_name not in self._services:
            raise KeyError(f"Service {service_name} not registered")
            
        service_def = self._services[service_name]
        
        # Return existing instance if singleton
        if service_def.singleton and service_def.instance is not None:
            return service_def.instance
            
        # Create new instance
        try:
            # Use factory if registered
            if service_name in self._factories:
                instance = self._factories[service_name]()
            else:
                instance = service_def.factory()
                
            # Store instance if singleton
            if service_def.singleton:
                service_def.instance = instance
                
            return instance
            
        except Exception as e:
            logger.error(f"Error resolving service {service_name}: {e}")
            raise
            
    def inject(self, service_type: Type[T]):
        """
        Decorator to inject a service into a function parameter.
        
        Args:
            service_type: Type of the service to inject
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get service instance
                service = self.resolve(service_type)
                
                # Add service to kwargs
                kwargs[service_type.__name__.lower()] = service
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
        
    def inject_many(self, *service_types: Type[T]):
        """
        Decorator to inject multiple services into function parameters.
        
        Args:
            *service_types: Types of services to inject
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get service instances
                for service_type in service_types:
                    service = self.resolve(service_type)
                    kwargs[service_type.__name__.lower()] = service
                    
                return func(*args, **kwargs)
            return wrapper
        return decorator
        
    def clear(self) -> None:
        """Clear all registered services and factories."""
        self._services.clear()
        self._factories.clear()
        
    def __enter__(self) -> 'Container':
        """Enter the container context."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the container context."""
        self.clear()
        
# Global container instance
container = Container()

def inject(service_type: Type[T]):
    """
    Decorator to inject a service using the global container.
    
    Args:
        service_type: Type of the service to inject
        
    Returns:
        Decorated function
    """
    return container.inject(service_type)
    
def inject_many(*service_types: Type[T]):
    """
    Decorator to inject multiple services using the global container.
    
    Args:
        *service_types: Types of services to inject
        
    Returns:
        Decorated function
    """
    return container.inject_many(*service_types) 