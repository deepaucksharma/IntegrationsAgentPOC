"""Monitoring and metrics collection."""
import logging
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.aiohttp import AioHttpClientInstrumentor

logger = logging.getLogger(__name__)

# Prometheus metrics
WORKFLOW_EXECUTIONS = Counter(
    'workflow_executions_total',
    'Total number of workflow executions',
    ['status', 'target', 'action']
)

WORKFLOW_DURATION = Histogram(
    'workflow_duration_seconds',
    'Duration of workflow executions',
    ['target', 'action'],
    buckets=(1, 5, 10, 30, 60, 120, 300)
)

ACTIVE_WORKFLOWS = Gauge(
    'active_workflows',
    'Number of currently active workflows',
    ['target']
)

DB_OPERATIONS = Counter(
    'db_operations_total',
    'Total number of database operations',
    ['operation', 'status']
)

DB_OPERATION_DURATION = Histogram(
    'db_operation_duration_seconds',
    'Duration of database operations',
    ['operation'],
    buckets=(0.1, 0.5, 1, 2, 5)
)

class MetricsCollector:
    """Collects and manages metrics."""
    
    def __init__(self, enable_tracing: bool = True):
        """Initialize the metrics collector."""
        self.enable_tracing = enable_tracing
        if enable_tracing:
            self._setup_tracing()
    
    def _setup_tracing(self) -> None:
        """Set up OpenTelemetry tracing."""
        try:
            # Set up tracer provider
            tracer_provider = TracerProvider()
            trace.set_tracer_provider(tracer_provider)
            
            # Set up meter provider
            meter_provider = MeterProvider()
            metrics.set_meter_provider(meter_provider)
            
            # Instrument SQLAlchemy
            SQLAlchemyInstrumentor().instrument()
            
            # Instrument aiohttp
            AioHttpClientInstrumentor().instrument()
            
            logger.info("Initialized OpenTelemetry tracing")
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
    
    def record_workflow_execution(
        self,
        status: str,
        target: str,
        action: str,
        duration: float
    ) -> None:
        """Record workflow execution metrics."""
        try:
            WORKFLOW_EXECUTIONS.labels(
                status=status,
                target=target,
                action=action
            ).inc()
            
            WORKFLOW_DURATION.labels(
                target=target,
                action=action
            ).observe(duration)
            
            if status == 'running':
                ACTIVE_WORKFLOWS.labels(target=target).inc()
            elif status == 'completed':
                ACTIVE_WORKFLOWS.labels(target=target).dec()
            
            logger.debug(f"Recorded workflow execution: {status} {target} {action}")
        except Exception as e:
            logger.error(f"Failed to record workflow metrics: {e}")
    
    def record_db_operation(
        self,
        operation: str,
        status: str,
        duration: float
    ) -> None:
        """Record database operation metrics."""
        try:
            DB_OPERATIONS.labels(
                operation=operation,
                status=status
            ).inc()
            
            DB_OPERATION_DURATION.labels(
                operation=operation
            ).observe(duration)
            
            logger.debug(f"Recorded DB operation: {operation} {status}")
        except Exception as e:
            logger.error(f"Failed to record DB metrics: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics values."""
        try:
            return {
                'workflow_executions': {
                    'total': WORKFLOW_EXECUTIONS._value.sum(),
                    'by_status': {
                        status: count
                        for status, count in WORKFLOW_EXECUTIONS._value.items()
                    }
                },
                'active_workflows': {
                    target: count
                    for target, count in ACTIVE_WORKFLOWS._value.items()
                },
                'db_operations': {
                    'total': DB_OPERATIONS._value.sum(),
                    'by_operation': {
                        op: count
                        for op, count in DB_OPERATIONS._value.items()
                    }
                }
            }
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {}
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        try:
            WORKFLOW_EXECUTIONS._value.clear()
            WORKFLOW_DURATION._value.clear()
            ACTIVE_WORKFLOWS._value.clear()
            DB_OPERATIONS._value.clear()
            DB_OPERATION_DURATION._value.clear()
            logger.info("Reset all metrics")
        except Exception as e:
            logger.error(f"Failed to reset metrics: {e}") 