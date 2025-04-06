from traceback import format_exc
from ..error.exceptions import DocumentationFetchError, ErrorContext

async def fetch_integration_docs(self, integration_type: str) -> Dict[str, Any]:
    """Fetches documentation with caching and fallback."""
    try:
        # ... existing code ...
        
        # If all approaches fail, return empty data with error flag
        logger.error(f"All URL approaches failed for {integration_type}")
        context = ErrorContext(
            component="DocumentationParser",
            operation="fetch_integration_docs",
            details={
                "integration_type": integration_type,
                "attempted_urls": url_patterns
            }
        )
        raise DocumentationFetchError(
            message=f"Failed to fetch documentation for {integration_type}",
            context=context
        )
        
    except DocumentationFetchError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in fetch_integration_docs: {e}")
        context = ErrorContext(
            component="DocumentationParser",
            operation="fetch_integration_docs",
            details={
                "integration_type": integration_type
            },
            traceback=format_exc()
        )
        raise DocumentationFetchError(
            message=f"Unexpected error while fetching documentation: {str(e)}",
            context=context
        ) from e 

async def _extract_structured_knowledge(self, content: str) -> Dict[str, Any]:
    """Extract structured knowledge from the documentation content."""
    try:
        # ... existing code ...
    except Exception as e:
        logger.error(f"Error extracting structured knowledge: {e}")
        context = ErrorContext(
            component="DocumentationParser",
            operation="_extract_structured_knowledge",
            details={
                "content_length": len(content)
            },
            traceback=format_exc()
        )
        raise DocumentationFetchError(
            message=f"Failed to extract structured knowledge: {str(e)}",
            context=context
        ) from e 