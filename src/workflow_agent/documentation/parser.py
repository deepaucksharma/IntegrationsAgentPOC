"""Module for fetching and parsing integration documentation."""
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class DocumentationParser:
    """Fetches and parses integration documentation from a given source."""
    
    def __init__(self, base_url: str = "https://docs.newrelic.com/install/"):
        self.base_url = base_url

    async def fetch_integration_docs(self, integration_type: str) -> Dict[str, Any]:
        """Fetches documentation for the specified integration type.
        
        Args:
            integration_type: The type of integration to fetch docs for
            
        Returns:
            Dict containing structured knowledge from the documentation
            
        Raises:
            Exception: If documentation fetch fails
        """
        url = f"{self.base_url}{integration_type}/"
        logger.info(f"Fetching documentation from {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        return await self._extract_structured_knowledge(content)
                    else:
                        raise Exception(f"Failed to fetch documentation for {integration_type}. Status: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching documentation: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing documentation: {e}")
            raise

    async def _extract_structured_knowledge(self, content: str) -> Dict[str, Any]:
        """Extracts structured data from raw HTML content.
        
        Args:
            content: Raw HTML content from documentation
            
        Returns:
            Dict containing parsed knowledge structure
        """
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract prerequisites
        prerequisites = self._extract_prerequisites(soup)
        
        # Extract installation methods
        installation_methods = self._extract_installation_methods(soup)
        
        # Extract configuration options
        config_options = self._extract_configuration_options(soup)
        
        # Extract verification steps
        verification_steps = self._extract_verification_steps(soup)
        
        return {
            "prerequisites": prerequisites,
            "installation_methods": installation_methods,
            "configuration_options": config_options,
            "verification_steps": verification_steps
        }

    def _extract_prerequisites(self, soup: BeautifulSoup) -> List[str]:
        """Extract prerequisites from documentation."""
        # Look for common prerequisite sections/headers
        prereq_sections = soup.find_all(['div', 'section'], 
                                      class_=lambda x: x and 'prerequisite' in x.lower())
        prerequisites = []
        for section in prereq_sections:
            items = section.find_all(['li', 'p'])
            prerequisites.extend([item.get_text().strip() for item in items if item.get_text().strip()])
        return prerequisites

    def _extract_installation_methods(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract available installation methods."""
        methods = []
        # Look for installation method sections
        install_sections = soup.find_all(['div', 'section'], 
                                       class_=lambda x: x and 'installation' in x.lower())
        
        for section in install_sections:
            method_name = section.find(['h2', 'h3', 'h4'])
            if method_name:
                steps = []
                for step in section.find_all(['li', 'code']):
                    step_text = step.get_text().strip()
                    if step_text:
                        steps.append(step_text)
                        
                methods.append({
                    "name": method_name.get_text().strip(),
                    "steps": steps,
                    "platform_compatibility": self._extract_platform_info(section)
                })
        
        return methods

    def _extract_configuration_options(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract configuration options and their requirements."""
        config_options = {}
        config_sections = soup.find_all(['div', 'section'], 
                                      class_=lambda x: x and 'configuration' in x.lower())
        
        for section in config_sections:
            # Look for configuration parameters in tables, lists, or paragraphs
            for elem in section.find_all(['tr', 'li']):
                option_name = elem.find(['th', 'strong', 'code'])
                if option_name:
                    name = option_name.get_text().strip()
                    description = elem.get_text().strip()
                    required = 'required' in description.lower()
                    config_options[name] = "required" if required else "optional"
        
        return config_options

    def _extract_verification_steps(self, soup: BeautifulSoup) -> List[str]:
        """Extract verification steps from documentation."""
        verify_sections = soup.find_all(['div', 'section'], 
                                      class_=lambda x: x and ('verify' in x.lower() or 
                                                            'validation' in x.lower()))
        steps = []
        for section in verify_sections:
            items = section.find_all(['li', 'p', 'code'])
            steps.extend([item.get_text().strip() for item in items if item.get_text().strip()])
        return steps

    def _extract_platform_info(self, section: BeautifulSoup) -> List[str]:
        """Extract platform compatibility information."""
        platforms = []
        platform_keywords = ['windows', 'linux', 'macos', 'ubuntu', 'centos', 'rhel']
        text = section.get_text().lower()
        
        for platform in platform_keywords:
            if platform in text:
                platforms.append(platform)
        
        return platforms 