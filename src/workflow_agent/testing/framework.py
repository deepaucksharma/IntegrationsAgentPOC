import os
import logging
import unittest
import tempfile
from typing import Any, Dict, List, Optional, Type, TypeVar
from pathlib import Path
import shutil
from contextlib import contextmanager
import json
import yaml

logger = logging.getLogger(__name__)

T = TypeVar('T')

class TestCase(unittest.TestCase):
    """Base test case with common functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, 'config')
        self.data_dir = os.path.join(self.temp_dir, 'data')
        self.log_dir = os.path.join(self.temp_dir, 'logs')
        
        # Create directories
        for directory in [self.config_dir, self.data_dir, self.log_dir]:
            Path(directory).mkdir(parents=True, exist_ok=True)
            
        # Set up logging
        self._setup_logging()
        
    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
        
    def _setup_logging(self):
        """Set up logging for tests."""
        log_file = os.path.join(self.log_dir, 'test.log')
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
    @contextmanager
    def temp_file(self, content: str = '', suffix: str = '.txt'):
        """
        Create a temporary file with content.
        
        Args:
            content: File content
            suffix: File suffix
            
        Yields:
            Path to temporary file
        """
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.temp_dir)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
            yield path
        finally:
            os.unlink(path)
            
    @contextmanager
    def temp_json(self, data: Dict[str, Any]):
        """
        Create a temporary JSON file.
        
        Args:
            data: JSON data
            
        Yields:
            Path to temporary file
        """
        with self.temp_file(json.dumps(data), '.json') as path:
            yield path
            
    @contextmanager
    def temp_yaml(self, data: Dict[str, Any]):
        """
        Create a temporary YAML file.
        
        Args:
            data: YAML data
            
        Yields:
            Path to temporary file
        """
        with self.temp_file(yaml.dump(data), '.yaml') as path:
            yield path
            
    def assert_file_exists(self, path: str):
        """
        Assert that a file exists.
        
        Args:
            path: File path
        """
        self.assertTrue(os.path.exists(path), f"File {path} does not exist")
        
    def assert_file_not_exists(self, path: str):
        """
        Assert that a file does not exist.
        
        Args:
            path: File path
        """
        self.assertFalse(os.path.exists(path), f"File {path} exists")
        
    def assert_file_content(self, path: str, content: str):
        """
        Assert file content matches expected content.
        
        Args:
            path: File path
            content: Expected content
        """
        with open(path, 'r') as f:
            actual_content = f.read()
        self.assertEqual(actual_content, content)
        
    def assert_json_content(self, path: str, data: Dict[str, Any]):
        """
        Assert JSON file content matches expected data.
        
        Args:
            path: File path
            data: Expected data
        """
        with open(path, 'r') as f:
            actual_data = json.load(f)
        self.assertEqual(actual_data, data)
        
    def assert_yaml_content(self, path: str, data: Dict[str, Any]):
        """
        Assert YAML file content matches expected data.
        
        Args:
            path: File path
            data: Expected data
        """
        with open(path, 'r') as f:
            actual_data = yaml.safe_load(f)
        self.assertEqual(actual_data, data)
        
class MockObject:
    """Mock object for testing."""
    
    def __init__(self, **kwargs):
        """Initialize mock object with attributes."""
        for key, value in kwargs.items():
            setattr(self, key, value)
            
    def __repr__(self):
        """String representation of mock object."""
        attrs = ', '.join(f'{k}={v}' for k, v in self.__dict__.items())
        return f'MockObject({attrs})'
        
class MockFunction:
    """Mock function for testing."""
    
    def __init__(self, return_value: Any = None):
        """
        Initialize mock function.
        
        Args:
            return_value: Value to return when called
        """
        self.return_value = return_value
        self.calls: List[tuple] = []
        
    def __call__(self, *args, **kwargs):
        """
        Call the mock function.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Return value
        """
        self.calls.append((args, kwargs))
        return self.return_value
        
    def assert_called(self, *args, **kwargs):
        """
        Assert that the function was called with specific arguments.
        
        Args:
            *args: Expected positional arguments
            **kwargs: Expected keyword arguments
        """
        for call_args, call_kwargs in self.calls:
            if call_args == args and call_kwargs == kwargs:
                return
        raise AssertionError(
            f"Function was not called with args={args}, kwargs={kwargs}\n"
            f"Actual calls: {self.calls}"
        )
        
    def assert_called_once(self, *args, **kwargs):
        """
        Assert that the function was called exactly once with specific arguments.
        
        Args:
            *args: Expected positional arguments
            **kwargs: Expected keyword arguments
        """
        if len(self.calls) != 1:
            raise AssertionError(
                f"Function was called {len(self.calls)} times, expected 1"
            )
        self.assert_called(*args, **kwargs)
        
    def assert_not_called(self):
        """Assert that the function was not called."""
        if self.calls:
            raise AssertionError(
                f"Function was called {len(self.calls)} times, expected 0"
            )
            
    def reset(self):
        """Reset the mock function."""
        self.calls.clear()
        
class TestSuite:
    """Test suite with common functionality."""
    
    def __init__(self):
        """Initialize the test suite."""
        self.test_cases: List[Type[TestCase]] = []
        
    def add_test_case(self, test_case: Type[TestCase]):
        """
        Add a test case to the suite.
        
        Args:
            test_case: Test case class
        """
        self.test_cases.append(test_case)
        
    def run(self, verbosity: int = 2) -> unittest.TestResult:
        """
        Run all test cases.
        
        Args:
            verbosity: Test verbosity level
            
        Returns:
            Test result
        """
        suite = unittest.TestSuite()
        for test_case in self.test_cases:
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(test_case))
        return unittest.TextTestRunner(verbosity=verbosity).run(suite)
        
# Global test suite instance
test_suite = TestSuite()

def test_case(cls: Type[TestCase]):
    """
    Decorator to add a test case to the global test suite.
    
    Args:
        cls: Test case class
        
    Returns:
        Test case class
    """
    test_suite.add_test_case(cls)
    return cls 