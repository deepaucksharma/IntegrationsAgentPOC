"""
Enhanced template manager with inheritance, caching, and conditional rendering support.
"""
import os
import json
import yaml
import logging
import re
import time
import copy
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from base64 import b64encode, b64decode
from datetime import datetime
import uuid
import hashlib

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound, meta

logger = logging.getLogger(__name__)

class TemplateCache:
    """
    Cache for rendered templates with time-based invalidation.
    """
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Initialize template cache.
        
        Args:
            max_size: Maximum number of templates in cache
            ttl: Time to live in seconds for cache entries
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl = ttl
        self.access_times: Dict[str, float] = {}
        
    def get(self, key: str) -> Optional[str]:
        """
        Get a cached template by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached template content or None if not found/expired
        """
        if key not in self.cache:
            return None
            
        # Check if expired
        current_time = time.time()
        if current_time - self.access_times[key] > self.ttl:
            # Expired, remove from cache
            del self.cache[key]
            del self.access_times[key]
            return None
            
        # Update access time
        self.access_times[key] = current_time
        return self.cache[key]
        
    def set(self, key: str, value: str) -> None:
        """
        Add a template to the cache.
        
        Args:
            key: Cache key
            value: Template content
        """
        # Check if cache is full
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Remove least recently used item
            lru_key = min(self.access_times, key=self.access_times.get)
            del self.cache[lru_key]
            del self.access_times[lru_key]
            
        # Add to cache
        current_time = time.time()
        self.cache[key] = value
        self.access_times[key] = current_time
        
    def invalidate(self, pattern: str = None) -> None:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Regex pattern to match against keys
        """
        if pattern:
            # Compile regex
            regex = re.compile(pattern)
            
            # Find keys to invalidate
            keys_to_remove = [key for key in self.cache if regex.search(key)]
            
            # Remove matching keys
            for key in keys_to_remove:
                del self.cache[key]
                del self.access_times[key]
                
            logger.debug(f"Invalidated {len(keys_to_remove)} cache entries matching pattern '{pattern}'")
        else:
            # Invalidate all
            self.cache.clear()
            self.access_times.clear()
            logger.debug("Invalidated entire template cache")

class TemplateManager:
    """
    Enhanced template manager with inheritance, caching, and conditional rendering.
    """
    
    def __init__(self, template_dirs: Optional[List[str]] = None, cache_enabled: bool = True):
        """
        Initialize template manager.
        
        Args:
            template_dirs: List of template directories to search
            cache_enabled: Whether to enable template caching
        """
        self.template_dirs = template_dirs or ["templates"]
        self.cache = TemplateCache() if cache_enabled else None
        self.env = self._create_environment()
        self.template_registry: Dict[str, Dict[str, Any]] = {}
        self.inheritance_map: Dict[str, List[str]] = {}
        
        # Initialize template registry
        self._init_template_registry()
        
    def _create_environment(self) -> Environment:
        """
        Create Jinja2 environment with custom filters and globals.
        
        Returns:
            Configured Jinja2 environment
        """
        loader = FileSystemLoader(self.template_dirs)
        env = Environment(
            loader=loader,
            extensions=['jinja2.ext.do', 'jinja2.ext.loopcontrols'],
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom filters
        env.filters.update({
            'to_yaml': lambda obj: yaml.dump(obj, default_flow_style=False),
            'to_json': lambda obj: json.dumps(obj, indent=2),
            'path_join': lambda paths: os.path.join(*paths) if isinstance(paths, list) else paths,
            'base64_encode': lambda s: b64encode(s.encode()).decode() if s else '',
            'base64_decode': lambda s: b64decode(s.encode()).decode() if s else '',
            'lower': lambda s: s.lower() if s else '',
            'upper': lambda s: s.upper() if s else '',
            'title': lambda s: s.title() if s else '',
            'strip': lambda s: s.strip() if s else '',
            'replace': lambda s, old, new: s.replace(old, new) if s else '',
            'join': lambda seq, sep='': sep.join(seq) if seq else '',
            'split': lambda s, sep=None: s.split(sep) if s else [],
            'to_bool': lambda v: bool(v),
            'format_date': lambda dt, fmt='%Y-%m-%d': dt.strftime(fmt) if dt else '',
            'default': lambda v, d='': v if v else d,
        })
        
        # Add global functions
        env.globals.update({
            'include_file': self._include_file,
            'now': datetime.now,
            'uuid': lambda: str(uuid.uuid4()),
            'env': lambda key, default='': os.environ.get(key, default),
            'is_windows': os.name == 'nt',
            'is_linux': os.name == 'posix',
            'platform': os.name,
            'exists': os.path.exists,
            'dirname': os.path.dirname,
            'basename': os.path.basename,
        })
        
        return env
        
    def _include_file(self, filename: str) -> str:
        """
        Include a file's contents directly.
        
        Args:
            filename: Path to file relative to template directories
            
        Returns:
            File contents or error message
        """
        for template_dir in self.template_dirs:
            file_path = os.path.join(template_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"Error reading included file {file_path}: {e}")
                    return f"# Error reading file: {str(e)}"
        return f"# File not found: {filename}"
        
    def _init_template_registry(self) -> None:
        """Initialize the template registry by scanning template directories."""
        for template_dir in self.template_dirs:
            self._scan_templates(template_dir)
            
        # Build inheritance map
        self._build_inheritance_map()
        
        logger.info(f"Initialized template registry with {len(self.template_registry)} templates")
        
    def _scan_templates(self, template_dir: str) -> None:
        """
        Scan a template directory for templates and build registry.
        
        Args:
            template_dir: Directory to scan
        """
        if not os.path.exists(template_dir):
            logger.warning(f"Template directory not found: {template_dir}")
            return
            
        for root, _, files in os.walk(template_dir):
            for file in files:
                if file.endswith(('.j2', '.jinja', '.jinja2', '.tpl')):
                    rel_path = os.path.relpath(os.path.join(root, file), template_dir)
                    
                    try:
                        # Load template
                        template_source = self.env.loader.get_source(self.env, rel_path)[0]
                        
                        # Extract template metadata
                        metadata = self._extract_template_metadata(template_source, rel_path)
                        
                        # Add to registry
                        self.template_registry[rel_path] = {
                            'path': rel_path,
                            'full_path': os.path.join(root, file),
                            'extends': metadata.get('extends'),
                            'blocks': metadata.get('blocks', []),
                            'requires': metadata.get('requires', []),
                            'tags': metadata.get('tags', []),
                            'platform': metadata.get('platform'),
                            'description': metadata.get('description', ''),
                            'version': metadata.get('version', '1.0'),
                            'last_modified': os.path.getmtime(os.path.join(root, file))
                        }
                        
                    except Exception as e:
                        logger.warning(f"Error loading template {rel_path}: {e}")
                        
    def _extract_template_metadata(self, source: str, rel_path: str) -> Dict[str, Any]:
        """
        Extract metadata from template source.
        
        Args:
            source: Template source code
            rel_path: Relative path to template
            
        Returns:
            Template metadata
        """
        metadata = {
            'blocks': [],
            'requires': [],
            'tags': [],
        }
        
        # Check for extends
        extends_match = re.search(r'{%\s*extends\s+[\'"]([^\'"]+)[\'"]', source)
        if extends_match:
            metadata['extends'] = extends_match.group(1)
            
        # Extract blocks
        for block_match in re.finditer(r'{%\s*block\s+([^\s%]+)[^%]*%}', source):
            metadata['blocks'].append(block_match.group(1))
            
        # Look for metadata block
        meta_match = re.search(r'{#\s*META\s*(.*?)\s*#}', source, re.DOTALL)
        if meta_match:
            try:
                meta_content = meta_match.group(1).strip()
                # Try to parse as YAML
                meta_data = yaml.safe_load(meta_content)
                if isinstance(meta_data, dict):
                    metadata.update(meta_data)
            except Exception as e:
                logger.warning(f"Error parsing metadata for {rel_path}: {e}")
                
        # Extract required parameters
        ast = self.env.parse(source)
        required_params = meta.find_undeclared_variables(ast)
        metadata['requires'] = list(required_params)
        
        # Extract platform from path
        if 'windows' in rel_path.lower() or 'win' in rel_path.lower():
            metadata['platform'] = 'windows'
        elif 'linux' in rel_path.lower() or 'unix' in rel_path.lower():
            metadata['platform'] = 'linux'
        
        return metadata
        
    def _build_inheritance_map(self) -> None:
        """Build template inheritance map for efficient lookups."""
        # Clear existing map
        self.inheritance_map = {}
        
        # First pass: build direct inheritance
        for template_name, template_info in self.template_registry.items():
            if template_info.get('extends'):
                parent = template_info['extends']
                if parent not in self.inheritance_map:
                    self.inheritance_map[parent] = []
                self.inheritance_map[parent].append(template_name)
                
        # Second pass: resolve transitive inheritance
        for parent in list(self.inheritance_map.keys()):
            self._resolve_inheritance(parent, set())
            
    def _resolve_inheritance(self, template_name: str, visited: Set[str]) -> List[str]:
        """
        Resolve template inheritance recursively.
        
        Args:
            template_name: Template to resolve
            visited: Set of already visited templates to avoid cycles
            
        Returns:
            List of all descendants
        """
        if template_name in visited:
            logger.warning(f"Inheritance cycle detected involving template {template_name}")
            return []
            
        visited.add(template_name)
        
        # Get direct children
        children = self.inheritance_map.get(template_name, [])
        
        # Get descendants of children
        all_descendants = children.copy()
        for child in children:
            descendants = self._resolve_inheritance(child, visited.copy())
            all_descendants.extend(descendants)
            
        # Update inheritance map with all descendants
        self.inheritance_map[template_name] = list(set(all_descendants))
        
        return all_descendants
        
    async def render_template(self, template_path: str, context: Dict[str, Any], use_cache: bool = True) -> str:
        """
        Render a template with the given context.
        
        Args:
            template_path: Path to template
            context: Template rendering context
            use_cache: Whether to use template cache
            
        Returns:
            Rendered template
        """
        # Check if template exists
        if not self._template_exists(template_path):
            raise TemplateNotFound(f"Template not found: {template_path}")
            
        # Create cache key
        cache_key = None
        if use_cache and self.cache:
            context_hash = hashlib.md5(json.dumps(context, sort_keys=True).encode()).hexdigest()
            cache_key = f"{template_path}:{context_hash}"
            
            # Check cache
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Using cached template: {template_path}")
                return cached
                
        try:
            # Load and render template
            template = self.env.get_template(template_path)
            
            # Validate context against required parameters
            self._validate_context(template_path, context)
            
            # Render template
            rendered = template.render(**context)
            
            # Cache rendered template
            if cache_key and self.cache:
                self.cache.set(cache_key, rendered)
                
            return rendered
            
        except Exception as e:
            logger.error(f"Error rendering template {template_path}: {e}")
            raise
            
    def _template_exists(self, template_path: str) -> bool:
        """Check if a template exists."""
        try:
            self.env.get_template(template_path)
            return True
        except TemplateNotFound:
            return False
            
    def _validate_context(self, template_path: str, context: Dict[str, Any]) -> None:
        """
        Validate context against template requirements.
        
        Args:
            template_path: Path to template
            context: Template rendering context
            
        Raises:
            ValueError if required parameters are missing
        """
        # Get template info
        template_info = self.template_registry.get(template_path)
        if not template_info:
            return
            
        # Check required parameters
        missing = []
        for param in template_info.get('requires', []):
            # Skip special variables
            if param.startswith(('_', 'range', 'dict', 'lipsum', 'cycler')):
                continue
                
            # Check if parameter is in context
            parts = param.split('.')
            value = context
            found = True
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    found = False
                    break
                    
            if not found:
                missing.append(param)
                
        if missing:
            logger.warning(f"Missing required parameters for template {template_path}: {missing}")
            # Don't raise error, as templates might have defaults or conditionals
            
    async def select_best_template(self, candidates: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[str]:
        """
        Select the best template from a list of candidates based on context.
        
        Args:
            candidates: List of template candidates with conditions
            context: Template rendering context
            
        Returns:
            Path to best matching template or None if no match
        """
        if not candidates:
            return None
            
        best_match = None
        best_score = -1
        
        for candidate in candidates:
            path = candidate.get("path")
            conditions = candidate.get("conditions", {})
            
            # Calculate match score
            score = self._evaluate_conditions(conditions, context)
            
            # Check if template exists
            if not self._template_exists(path):
                logger.warning(f"Template not found: {path}")
                continue
                
            # Update best match if better score
            if score > best_score:
                best_score = score
                best_match = path
                
        return best_match
        
    def _evaluate_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> int:
        """
        Evaluate conditions against context to get a match score.
        
        Args:
            conditions: Condition dictionary
            context: Context to evaluate against
            
        Returns:
            Match score (higher is better)
        """
        if not conditions:
            return 0  # Baseline score for no conditions
            
        score = 0
        for key, condition in conditions.items():
            # Get context value
            key_parts = key.split('.')
            value = context
            for part in key_parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
                    
            # Skip if value not found
            if value is None:
                continue
                
            # Check condition
            if isinstance(condition, dict):
                # Complex condition
                if "eq" in condition and value == condition["eq"]:
                    score += 10
                elif "not_eq" in condition and value != condition["not_eq"]:
                    score += 10
                elif "contains" in condition and condition["contains"] in value:
                    score += 5
                elif "not_contains" in condition and condition["not_contains"] not in value:
                    score += 5
                elif "regex" in condition and re.search(condition["regex"], str(value)):
                    score += 8
                elif "gt" in condition and value > condition["gt"]:
                    score += 7
                elif "lt" in condition and value < condition["lt"]:
                    score += 7
                elif "gte" in condition and value >= condition["gte"]:
                    score += 7
                elif "lte" in condition and value <= condition["lte"]:
                    score += 7
                elif "in" in condition and value in condition["in"]:
                    score += 9
                elif "not_in" in condition and value not in condition["not_in"]:
                    score += 9
            else:
                # Simple equality condition
                if value == condition:
                    score += 10
                    
        return score
        
    async def find_templates_for_integration(self, integration_type: str, action: str, system_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find templates suitable for a specific integration and action.
        
        Args:
            integration_type: Type of integration
            action: Action to perform
            system_context: System context
            
        Returns:
            List of matching templates with metadata
        """
        # Determine platform
        is_windows = system_context.get("is_windows", os.name == 'nt')
        platform = "windows" if is_windows else "linux"
        
        # Possible template locations in order of preference
        patterns = [
            # 1. Integration-specific template for action and platform
            f"{integration_type}/{action}_{platform}",
            
            # 2. Integration-specific template for action
            f"{integration_type}/{action}",
            
            # 3. Common template for action and platform
            f"common/{action}_{platform}",
            
            # 4. Common template for action
            f"common/{action}",
            
            # 5. Generic template
            f"generic/{action}"
        ]
        
        # Find matching templates
        matches = []
        
        for pattern in patterns:
            for template_path, template_info in self.template_registry.items():
                if template_path.startswith(pattern):
                    # Check platform compatibility
                    template_platform = template_info.get('platform')
                    if template_platform and template_platform != platform:
                        continue
                        
                    # Check file extension
                    if not template_path.endswith(('.j2', '.jinja', '.jinja2', '.tpl')):
                        continue
                        
                    # Add to matches
                    matches.append({
                        "path": template_path,
                        "metadata": template_info,
                        "pattern_match": pattern,
                        "score": len(pattern)  # Longer pattern = more specific = higher score
                    })
                    
        # Sort by score (descending)
        matches.sort(key=lambda m: m["score"], reverse=True)
        
        return matches

    def get_template_required_params(self, template_path: str) -> List[str]:
        """
        Get list of required parameters for a template.
        
        Args:
            template_path: Path to template
            
        Returns:
            List of required parameter names
        """
        # Get template info
        template_info = self.template_registry.get(template_path)
        if template_info:
            return template_info.get('requires', [])
            
        # Template not in registry, parse it directly
        try:
            template_source = self.env.loader.get_source(self.env, template_path)[0]
            ast = self.env.parse(template_source)
            return list(meta.find_undeclared_variables(ast))
        except Exception as e:
            logger.warning(f"Error getting required parameters for {template_path}: {e}")
            return []
            
    def reload_templates(self) -> None:
        """Reload templates from disk and rebuild registry."""
        # Clear caches
        if self.cache:
            self.cache.invalidate()
            
        # Reload environment
        self.env = self._create_environment()
        
        # Clear registry
        self.template_registry.clear()
        self.inheritance_map.clear()
        
        # Rebuild registry
        self._init_template_registry()
        
        logger.info("Template registry reloaded")
