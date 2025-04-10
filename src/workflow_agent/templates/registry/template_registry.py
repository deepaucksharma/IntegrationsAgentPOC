"""
Unified template registry for centralized template management.
"""
import logging
import os
import json
from typing import Dict, Any, Optional, List, Set
from pathlib import Path
import time
import hashlib

logger = logging.getLogger(__name__)

class TemplateInfo:
    """Information about a template."""
    
    def __init__(
        self,
        template_id: str,
        template_path: str,
        template_type: str,
        integration_type: Optional[str] = None,
        actions: Optional[List[str]] = None,
        platform: Optional[str] = None,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None
    ):
        self.template_id = template_id
        self.template_path = template_path
        self.template_type = template_type
        self.integration_type = integration_type
        self.actions = actions or []
        self.platform = platform
        self.description = description
        self.variables = variables or []
        self.last_modified = os.path.getmtime(template_path) if os.path.exists(template_path) else 0
        self.content_hash = self._compute_hash()
        
    def _compute_hash(self) -> str:
        """Compute a hash of the template content."""
        if not os.path.exists(self.template_path):
            return ""
            
        with open(self.template_path, 'rb') as f:
            content = f.read()
            return hashlib.md5(content).hexdigest()
            
    def is_modified(self) -> bool:
        """Check if the template file has been modified."""
        if not os.path.exists(self.template_path):
            return False
            
        current_mtime = os.path.getmtime(self.template_path)
        if current_mtime > self.last_modified:
            current_hash = self._compute_hash()
            if current_hash != self.content_hash:
                self.last_modified = current_mtime
                self.content_hash = current_hash
                return True
                
        return False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "template_id": self.template_id,
            "template_path": self.template_path,
            "template_type": self.template_type,
            "integration_type": self.integration_type,
            "actions": self.actions,
            "platform": self.platform,
            "description": self.description,
            "variables": self.variables,
            "last_modified": self.last_modified,
            "content_hash": self.content_hash
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TemplateInfo':
        """Create from dictionary."""
        template_info = cls(
            template_id=data["template_id"],
            template_path=data["template_path"],
            template_type=data["template_type"],
            integration_type=data.get("integration_type"),
            actions=data.get("actions"),
            platform=data.get("platform"),
            description=data.get("description"),
            variables=data.get("variables")
        )
        template_info.last_modified = data.get("last_modified", 0)
        template_info.content_hash = data.get("content_hash", "")
        return template_info

class TemplateRegistry:
    """Centralized registry for templates."""
    
    def __init__(self, template_dirs: Optional[List[str]] = None):
        """
        Initialize the template registry.
        
        Args:
            template_dirs: Directories to scan for templates
        """
        self.template_dirs = template_dirs or []
        self.templates: Dict[str, TemplateInfo] = {}
        self.integration_templates: Dict[str, Dict[str, List[str]]] = {}
        self.index_path = "templates/registry/index.json"
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        
        # Load existing index if available
        self._load_index()
        
    def _load_index(self) -> None:
        """Load template index from disk."""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r') as f:
                    data = json.load(f)
                    
                    for template_data in data.get("templates", []):
                        template_info = TemplateInfo.from_dict(template_data)
                        self.templates[template_info.template_id] = template_info
                        
                    self.integration_templates = data.get("integration_templates", {})
                    
                logger.info(f"Loaded {len(self.templates)} templates from index")
            except Exception as e:
                logger.error(f"Failed to load template index: {e}")
        
    def _save_index(self) -> None:
        """Save template index to disk."""
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            
            data = {
                "templates": [template.to_dict() for template in self.templates.values()],
                "integration_templates": self.integration_templates
            }
            
            with open(self.index_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug("Saved template index")
        except Exception as e:
            logger.error(f"Failed to save template index: {e}")
    
    def scan_templates(self) -> None:
        """Scan template directories and update registry."""
        # Track new and modified templates
        new_templates = []
        modified_templates = []
        
        # Check existing templates for modifications
        for template_id, template_info in list(self.templates.items()):
            if template_info.is_modified():
                logger.debug(f"Template modified: {template_id}")
                modified_templates.append(template_id)
            elif not os.path.exists(template_info.template_path):
                logger.debug(f"Template removed: {template_id}")
                self._remove_template(template_id)
        
        # Scan directories for new templates
        for template_dir in self.template_dirs:
            if not os.path.exists(template_dir):
                logger.warning(f"Template directory not found: {template_dir}")
                continue
                
            for root, _, files in os.walk(template_dir):
                for filename in files:
                    # Skip non-template files
                    if not (filename.endswith('.j2') or filename.endswith('.jinja') or filename.endswith('.tmpl')):
                        continue
                        
                    template_path = os.path.join(root, filename)
                    template_id = self._generate_template_id(template_path)
                    
                    if template_id not in self.templates:
                        logger.debug(f"New template found: {template_id}")
                        template_info = self._parse_template_metadata(template_path)
                        if template_info:
                            self.templates[template_id] = template_info
                            new_templates.append(template_id)
        
        # Rebuild integration templates index
        self._rebuild_integration_index()
        
        # Save index if there were changes
        if new_templates or modified_templates:
            logger.info(f"Template scan: {len(new_templates)} new, {len(modified_templates)} modified")
            self._save_index()
    
    def _generate_template_id(self, template_path: str) -> str:
        """Generate a unique template ID from path."""
        # Use relative path as ID
        for template_dir in self.template_dirs:
            if template_path.startswith(template_dir):
                relative_path = os.path.relpath(template_path, template_dir)
                return relative_path.replace('\\', '/').replace(' ', '_')
                
        # Fallback to filename
        return os.path.basename(template_path)
    
    def _parse_template_metadata(self, template_path: str) -> Optional[TemplateInfo]:
        """Parse template metadata from file."""
        try:
            # Attempt to extract metadata from template content
            template_id = self._generate_template_id(template_path)
            
            # Default template type based on directory structure
            path_parts = Path(template_path).parts
            template_type = "script"
            integration_type = None
            actions = []
            platform = None
            
            # Try to infer metadata from path
            for i, part in enumerate(path_parts):
                if part.lower() == "templates":
                    if i + 1 < len(path_parts):
                        template_type = path_parts[i + 1].lower()
                    if i + 2 < len(path_parts):
                        integration_type = path_parts[i + 2].lower()
                elif part.lower() in ["install", "verify", "uninstall", "configure"]:
                    actions.append(part.lower())
                elif part.lower() in ["windows", "linux", "macos", "darwin"]:
                    platform = part.lower()
            
            # Extract variables from template content
            variables = self._extract_template_variables(template_path)
            
            # Create template info
            return TemplateInfo(
                template_id=template_id,
                template_path=template_path,
                template_type=template_type,
                integration_type=integration_type,
                actions=actions,
                platform=platform,
                description=None,
                variables=variables
            )
        except Exception as e:
            logger.error(f"Failed to parse template metadata for {template_path}: {e}")
            return None
    
    def _extract_template_variables(self, template_path: str) -> List[str]:
        """Extract variable names from template content."""
        variables = set()
        
        try:
            with open(template_path, 'r') as f:
                content = f.read()
                
            # Simple regex patterns for variables
            import re
            
            # Jinja2 variable pattern: {{ variable }}
            for match in re.finditer(r'{{\s*(\w+)\s*}}', content):
                variables.add(match.group(1))
                
            # Jinja2 for loop pattern: {% for x in collection %}
            for match in re.finditer(r'{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%}', content):
                variables.add(match.group(2))
                
            # Jinja2 if pattern: {% if variable %}
            for match in re.finditer(r'{%\s*if\s+(\w+)\s*[}|==|!=|>|<]', content):
                variables.add(match.group(1))
                
        except Exception as e:
            logger.error(f"Failed to extract variables from {template_path}: {e}")
            
        return list(variables)
    
    def _remove_template(self, template_id: str) -> None:
        """Remove a template from the registry."""
        if template_id in self.templates:
            del self.templates[template_id]
            
            # Remove from integration templates index
            for integration, actions in list(self.integration_templates.items()):
                for action, templates in list(actions.items()):
                    if template_id in templates:
                        templates.remove(template_id)
                        if not templates:
                            del actions[action]
                if not actions:
                    del self.integration_templates[integration]
    
    def _rebuild_integration_index(self) -> None:
        """Rebuild the integration templates index."""
        self.integration_templates = {}
        
        for template_id, template_info in self.templates.items():
            if not template_info.integration_type:
                continue
                
            integration = template_info.integration_type
            if integration not in self.integration_templates:
                self.integration_templates[integration] = {}
                
            for action in template_info.actions or ["default"]:
                if action not in self.integration_templates[integration]:
                    self.integration_templates[integration][action] = []
                    
                if template_id not in self.integration_templates[integration][action]:
                    self.integration_templates[integration][action].append(template_id)
    
    def get_template(self, template_id: str) -> Optional[TemplateInfo]:
        """
        Get template information by ID.
        
        Args:
            template_id: Template ID
            
        Returns:
            Template information or None if not found
        """
        return self.templates.get(template_id)
    
    def get_template_content(self, template_id: str) -> Optional[str]:
        """
        Get template content by ID.
        
        Args:
            template_id: Template ID
            
        Returns:
            Template content or None if not found
        """
        template_info = self.get_template(template_id)
        if not template_info:
            return None
            
        try:
            with open(template_info.template_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read template {template_id}: {e}")
            return None
    
    def find_templates(
        self,
        integration_type: Optional[str] = None,
        action: Optional[str] = None,
        platform: Optional[str] = None,
        template_type: Optional[str] = None
    ) -> List[TemplateInfo]:
        """
        Find templates matching criteria.
        
        Args:
            integration_type: Integration type
            action: Action
            platform: Platform
            template_type: Template type
            
        Returns:
            List of matching templates
        """
        results = []
        
        # Fast path using index if integration and action are specified
        if integration_type and action:
            if integration_type in self.integration_templates and action in self.integration_templates[integration_type]:
                template_ids = self.integration_templates[integration_type][action]
                for template_id in template_ids:
                    template_info = self.templates.get(template_id)
                    if template_info and self._matches_criteria(template_info, platform, template_type):
                        results.append(template_info)
                return results
        
        # Slower path - scan all templates
        for template_info in self.templates.values():
            if (not integration_type or template_info.integration_type == integration_type) and \
               (not action or action in template_info.actions) and \
               self._matches_criteria(template_info, platform, template_type):
                results.append(template_info)
                
        return results
    
    def _matches_criteria(
        self,
        template_info: TemplateInfo,
        platform: Optional[str],
        template_type: Optional[str]
    ) -> bool:
        """Check if template matches platform and type criteria."""
        return (not platform or not template_info.platform or template_info.platform == platform) and \
               (not template_type or template_info.template_type == template_type)
    
    def add_template(self, template_path: str) -> Optional[str]:
        """
        Add a template to the registry.
        
        Args:
            template_path: Path to template file
            
        Returns:
            Template ID if added successfully, None otherwise
        """
        if not os.path.exists(template_path):
            logger.error(f"Template file not found: {template_path}")
            return None
            
        template_id = self._generate_template_id(template_path)
        template_info = self._parse_template_metadata(template_path)
        
        if template_info:
            self.templates[template_id] = template_info
            self._rebuild_integration_index()
            self._save_index()
            logger.info(f"Added template: {template_id}")
            return template_id
            
        return None
    
    def remove_template_by_path(self, template_path: str) -> bool:
        """
        Remove a template by path.
        
        Args:
            template_path: Path to template file
            
        Returns:
            True if removed, False otherwise
        """
        template_id = self._generate_template_id(template_path)
        if template_id in self.templates:
            self._remove_template(template_id)
            self._save_index()
            logger.info(f"Removed template: {template_id}")
            return True
            
        return False
