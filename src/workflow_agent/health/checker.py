"""Health check functionality."""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from ..storage import HistoryManager
from ..error.exceptions import DatabaseError, ResourceError

logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    """Health status information."""
    is_healthy: bool
    status: str
    details: Dict[str, Any]
    timestamp: datetime

class HealthChecker:
    """Performs health checks on the system."""
    
    def __init__(self, history_manager: HistoryManager):
        """Initialize the health checker."""
        self.history_manager = history_manager
        self.last_check: Optional[datetime] = None
        self.check_interval = timedelta(minutes=5)
    
    async def check_health(self) -> HealthStatus:
        """Perform a comprehensive health check."""
        try:
            # Check database connectivity
            db_status = await self._check_database()
            
            # Check resource usage
            resource_status = await self._check_resources()
            
            # Check recent executions
            execution_status = await self._check_recent_executions()
            
            # Determine overall health
            is_healthy = all([
                db_status['is_healthy'],
                resource_status['is_healthy'],
                execution_status['is_healthy']
            ])
            
            status = "healthy" if is_healthy else "unhealthy"
            
            details = {
                'database': db_status,
                'resources': resource_status,
                'executions': execution_status
            }
            
            self.last_check = datetime.utcnow()
            
            return HealthStatus(
                is_healthy=is_healthy,
                status=status,
                details=details,
                timestamp=self.last_check
            )
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                is_healthy=False,
                status="error",
                details={'error': str(e)},
                timestamp=datetime.utcnow()
            )
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = datetime.utcnow()
            await self.history_manager.get_execution_history(limit=1)
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                'is_healthy': True,
                'status': 'connected',
                'latency': duration,
                'last_check': datetime.utcnow().isoformat()
            }
        except DatabaseError as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'is_healthy': False,
                'status': 'error',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            is_healthy = (
                cpu_percent < 90 and
                memory.percent < 90 and
                disk.percent < 90
            )
            
            return {
                'is_healthy': is_healthy,
                'status': 'ok' if is_healthy else 'warning',
                'metrics': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'disk_percent': disk.percent
                },
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Resource health check failed: {e}")
            return {
                'is_healthy': False,
                'status': 'error',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_recent_executions(self) -> Dict[str, Any]:
        """Check recent workflow executions."""
        try:
            recent_executions = await self.history_manager.get_execution_history(
                limit=10,
                start_time=datetime.utcnow() - timedelta(hours=1)
            )
            
            if not recent_executions:
                return {
                    'is_healthy': True,
                    'status': 'ok',
                    'message': 'No recent executions',
                    'last_check': datetime.utcnow().isoformat()
                }
            
            success_rate = sum(1 for e in recent_executions if e['success']) / len(recent_executions)
            is_healthy = success_rate >= 0.9
            
            return {
                'is_healthy': is_healthy,
                'status': 'ok' if is_healthy else 'warning',
                'metrics': {
                    'total_executions': len(recent_executions),
                    'success_rate': success_rate,
                    'failure_rate': 1 - success_rate
                },
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Execution health check failed: {e}")
            return {
                'is_healthy': False,
                'status': 'error',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    def should_check(self) -> bool:
        """Determine if a health check should be performed."""
        if not self.last_check:
            return True
        return datetime.utcnow() - self.last_check >= self.check_interval 