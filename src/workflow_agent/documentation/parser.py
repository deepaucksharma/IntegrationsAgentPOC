import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class DocumentationParser:
    """Fetches and parses integration documentation from New Relic."""
    def __init__(self, base_url: str = "https://docs.newrelic.com/install/"):
        self.base_url = base_url

    async def fetch_integration_docs(self, integration_type: str) -> Dict[str, Any]:
        url = f"{self.base_url}{integration_type}/"
        logger.info(f"Fetching documentation from {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch docs: HTTP {response.status}")
                content = await response.text()
                return self._extract_structured_knowledge(content)

    def _extract_structured_knowledge(self, content: str) -> Dict[str, Any]:
        soup = BeautifulSoup(content, 'lxml')
        prerequisites = self._extract_prerequisites(soup)
        installation_methods = self._extract_installation_methods(soup)
        config_options = self._extract_configuration_options(soup)
        verification_steps = self._extract_verification_steps(soup)
        return {
            "prerequisites": prerequisites,
            "installation_methods": installation_methods,
            "configuration_options": config_options,
            "verification_steps": verification_steps
        }

    def _extract_prerequisites(self, soup: BeautifulSoup) -> List[str]:
        prereq_sections = soup.find_all(lambda tag: tag.name in ['div','section'] and tag.get_text().lower().find("before you begin") != -1)
        prerequisites = []
        for section in prereq_sections:
            prerequisites.extend([item.get_text().strip() for item in section.find_all(['li','p'])])
        return prerequisites

    def _extract_installation_methods(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        methods = []
        install_sections = soup.find_all(lambda tag: tag.name in ['div','section'] and tag.get_text().lower().find("installation") != -1)
        for section in install_sections:
            header = section.find(['h2','h3','h4'])
            if header:
                steps = [step.get_text().strip() for step in section.find_all('li')]
                methods.append({
                    "name": header.get_text().strip(),
                    "steps": steps,
                    "platform_compatibility": self._extract_platform_info(section)
                })
        return methods

    def _extract_platform_info(self, section: BeautifulSoup) -> List[str]:
        platforms = []
        text = section.get_text().lower()
        for os in ["windows", "linux", "macos"]:
            if os in text:
                platforms.append(os)
        return platforms

    def _extract_configuration_options(self, soup: BeautifulSoup) -> Dict[str, str]:
        config_options = {}
        config_sections = soup.find_all(lambda tag: tag.name in ['div','section'] and "configuration" in tag.get_text().lower())
        for section in config_sections:
            for row in section.find_all('tr'):
                cols = row.find_all(['th','td'])
                if cols and len(cols) >= 2:
                    option = cols[0].get_text().strip()
                    desc = cols[1].get_text().strip()
                    config_options[option] = "required" if "required" in desc.lower() else "optional"
        return config_options

    def _extract_verification_steps(self, soup: BeautifulSoup) -> List[str]:
        verify_sections = soup.find_all(lambda tag: tag.name in ['div','section'] and ("verify" in tag.get_text().lower() or "validation" in tag.get_text().lower()))
        steps = []
        for section in verify_sections:
            steps.extend([item.get_text().strip() for item in section.find_all(['li','p','code'])])
        return steps