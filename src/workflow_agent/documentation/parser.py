"""Module for fetching and parsing integration documentation."""
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import logging
import re

logger = logging.getLogger(__name__)

class DocumentationParser:
    """Fetches and parses integration documentation from New Relic."""
    
    def __init__(self, base_url: str = "https://docs.newrelic.com/docs/infrastructure/choose-infra-install-method/"):
        self.base_url = base_url

    async def fetch_integration_docs(self, integration_type: str) -> Dict[str, Any]:
        """Fetches documentation for the specified integration type."""
        url = f"{self.base_url}{integration_type}/"
        logger.info(f"Fetching documentation from {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        return await self._extract_structured_knowledge(content)
                    else:
                        # Try alternative URL formats
                        alt_urls = [
                            f"https://docs.newrelic.com/docs/infrastructure/install/{integration_type}/",
                            f"https://docs.newrelic.com/docs/infrastructure/install/agents/{integration_type}/",
                            f"https://docs.newrelic.com/docs/infrastructure/host-integrations/{integration_type}/"
                        ]
                        
                        for alt_url in alt_urls:
                            logger.info(f"Trying alternative URL: {alt_url}")
                            try:
                                async with session.get(alt_url) as alt_response:
                                    if alt_response.status == 200:
                                        content = await alt_response.text()
                                        return await self._extract_structured_knowledge(content)
                            except Exception as e:
                                logger.debug(f"Error with alternative URL {alt_url}: {e}")
                        
                        # If direct approaches fail, try search
                        logger.warning(f"Direct URLs failed with status {response.status}, trying search approach")
                        search_results = await self._search_documentation(integration_type, session)
                        if search_results:
                            async with session.get(search_results[0]) as doc_response:
                                if doc_response.status == 200:
                                    content = await doc_response.text()
                                    return await self._extract_structured_knowledge(content)
                        
                        # If all approaches fail, return mock data for testing
                        logger.warning(f"All URL approaches failed, using mock data for {integration_type}")
                        return self._generate_mock_data(integration_type)
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching documentation: {e}")
            return self._generate_mock_data(integration_type)
        except Exception as e:
            logger.error(f"Error processing documentation: {e}")
            return self._generate_mock_data(integration_type)

    async def _extract_structured_knowledge(self, content: str) -> Dict[str, Any]:
        """Extract structured knowledge from the documentation content."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            # Implementation details would go here
            return {"content": content}  # Placeholder
        except Exception as e:
            logger.error(f"Error extracting structured knowledge: {e}")
            return {}

    async def _search_documentation(self, integration_type: str, session: aiohttp.ClientSession) -> List[str]:
        """Search for documentation URLs."""
        try:
            search_url = f"https://docs.newrelic.com/api/search?query={integration_type}+integration+install"
            async with session.get(search_url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract relevant URLs from search results
                    return [result['url'] for result in data.get('results', [])][:1]
                return []
        except Exception as e:
            logger.error(f"Error searching documentation: {e}")
            return []

    def _generate_mock_data(self, integration_type: str) -> Dict[str, Any]:
        """Generate mock data for testing purposes."""
        return {
            "integration_type": integration_type,
            "mock": True,
            "installation_steps": [
                "Download the integration package",
                "Configure the integration",
                "Start the integration service"
            ]
        }