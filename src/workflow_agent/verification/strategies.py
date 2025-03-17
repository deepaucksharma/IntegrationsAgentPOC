import os
import re
import logging
import json
import asyncio
import aiohttp
import tempfile
import time
from typing import Dict, Any, Optional, List, Callable, Awaitable

from ..core.state import WorkflowState

logger = logging.getLogger(__name__)

# Strategy names
SERVICE_CHECK = "service_check"
HTTP_CHECK = "http_check"
LOG_CHECK = "log_check"
PROCESS_CHECK = "process_check"
API_CHECK = "api_check"

# Registry of verification strategies
VERIFICATION_STRATEGIES: Dict[str, Callable] = {}

def register_verification_strategy(name: str, strategy: Callable) -> None:
    """
    Register a verification strategy.
    
    Args:
        name: Strategy name
        strategy: Strategy function
    """
    VERIFICATION_STRATEGIES[name] = strategy
    logger.debug(f"Registered verification strategy: {name}")

def get_verification_strategy(name: str) -> Optional[Callable]:
    """
    Get a verification strategy by name.
    
    Args:
        name: Strategy name
        
    Returns:
        Strategy function or None if not found
    """
    return VERIFICATION_STRATEGIES.get(name)

async def service_check_strategy(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check if a service is running.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with verification results
    """
    # Determine the service name
    service_name = None
    
    # Try to extract from target name
    if state.target_name:
        service_name = state.target_name
    
    # If target is a full product name, try to extract core service
    common_services = {
        "postgresql": "postgresql",
        "postgres": "postgresql",
        "mysql": "mysql",
        "redis": "redis",
        "mongodb": "mongod",
        "nginx": "nginx",
        "apache": "httpd",
        "newrelic": "newrelic-infra"
    }
    
    for service_key, service_value in common_services.items():
        if service_key in state.target_name:
            service_name = service_value
            break
    
    # Check if service exists
    if not service_name:
        return {
            "success": False,
            "message": "Could not determine service name",
            "service": None
        }
    
    try:
        # Try systemctl
        process = await asyncio.create_subprocess_exec(
            "systemctl", "is-active", service_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            status = stdout.decode().strip()
            if status == "active":
                return {
                    "success": True,
                    "message": f"Service {service_name} is active",
                    "service": service_name,
                    "status": status
                }
            else:
                return {
                    "success": False,
                    "message": f"Service {service_name} is not active (status: {status})",
                    "service": service_name,
                    "status": status
                }
        
        # Try service command as fallback
        process = await asyncio.create_subprocess_exec(
            "service", service_name, "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {
                "success": True,
                "message": f"Service {service_name} is running",
                "service": service_name,
                "output": stdout.decode()
            }
        
        return {
            "success": False,
            "message": f"Service {service_name} is not running",
            "service": service_name,
            "output": stdout.decode()
        }
    except Exception as e:
        logger.error(f"Error checking service status: {e}")
        return {
            "success": False,
            "message": f"Error checking service status: {str(e)}",
            "service": service_name
        }

async def http_check_strategy(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check if an HTTP service is responding.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with verification results
    """
    # Determine the URL to check
    port = state.parameters.get("port", 80)
    host = state.parameters.get("host", "localhost")
    path = state.parameters.get("path", "/")
    protocol = "https" if state.parameters.get("ssl", False) else "http"
    
    url = f"{protocol}://{host}:{port}{path}"
    
    try:
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            async with session.get(url, timeout=10) as response:
                elapsed = time.time() - start_time
                
                if response.status < 400:
                    return {
                        "success": True,
                        "message": f"HTTP check succeeded: {response.status}",
                        "url": url,
                        "status": response.status,
                        "response_time": elapsed
                    }
                else:
                    return {
                        "success": False,
                        "message": f"HTTP check failed: {response.status}",
                        "url": url,
                        "status": response.status,
                        "response_time": elapsed
                    }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "message": f"HTTP check timed out: {url}",
            "url": url
        }
    except Exception as e:
        logger.error(f"Error performing HTTP check: {e}")
        return {
            "success": False,
            "message": f"Error performing HTTP check: {str(e)}",
            "url": url
        }

async def log_check_strategy(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check logs for successful operation.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with verification results
    """
    # Determine log file to check based on target
    log_file = None
    check_pattern = None
    
    target = state.target_name.lower()
    
    # Common log files
    if "postgres" in target:
        log_file = "/var/log/postgresql/postgresql-*.log"
        check_pattern = "database system is ready to accept connections"
    elif "mysql" in target:
        log_file = "/var/log/mysql/error.log"
        check_pattern = "ready for connections"
    elif "nginx" in target:
        log_file = "/var/log/nginx/error.log"
        check_pattern = "start worker process"
    elif "apache" in target or "httpd" in target:
        log_file = "/var/log/httpd/error_log"
        check_pattern = "resuming normal operations"
    elif "newrelic" in target:
        log_file = "/var/log/newrelic-infra/newrelic-infra.log"
        check_pattern = "Connected to New Relic platform"
    else:
        log_file = f"/var/log/{target}*.log"
        check_pattern = "(started|running|ready|connected)"
    
    # Override with parameters if provided
    if state.parameters.get("log_file"):
        log_file = state.parameters.get("log_file")
    
    if state.parameters.get("log_pattern"):
        check_pattern = state.parameters.get("log_pattern")
    
    if not log_file or not check_pattern:
        return {
            "success": False,
            "message": "Could not determine log file or pattern",
            "log_file": log_file,
            "pattern": check_pattern
        }
    
    try:
        # Create a temporary script to check logs
        temp_dir = tempfile.mkdtemp(prefix='workflow-log-check-')
        script_path = os.path.join(temp_dir, "check_logs.sh")
        
        with open(script_path, 'w') as f:
            f.write(f"""#!/usr/bin/env bash
set -e
if ls {log_file} 2>/dev/null >/dev/null; then
    if grep -q "{check_pattern}" {log_file}; then
        echo "Pattern found in log file"
        exit 0
    else
        echo "Pattern not found in log file"
        exit 1
    fi
else
    echo "Log file not found"
    exit 2
fi
""")
        
        os.chmod(script_path, 0o755)
        
        # Execute script
        process = await asyncio.create_subprocess_exec(
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {
                "success": True,
                "message": "Log check successful: pattern found",
                "log_file": log_file,
                "pattern": check_pattern,
                "output": stdout.decode()
            }
        else:
            return {
                "success": False,
                "message": f"Log check failed: {stdout.decode()}",
                "log_file": log_file,
                "pattern": check_pattern,
                "output": stdout.decode()
            }
    except Exception as e:
        logger.error(f"Error performing log check: {e}")
        return {
            "success": False,
            "message": f"Error performing log check: {str(e)}",
            "log_file": log_file,
            "pattern": check_pattern
        }
    finally:
        # Cleanup
        try:
            if os.path.exists(script_path):
                os.unlink(script_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up log check script: {e}")

async def process_check_strategy(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check if a process is running.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with verification results
    """
    # Determine process name to check
    process_name = None
    
    # Map targets to process names
    process_map = {
        "postgres": "postgres",
        "postgresql": "postgres",
        "mysql": "mysqld",
        "redis": "redis-server",
        "mongodb": "mongod",
        "nginx": "nginx",
        "apache": "httpd",
        "httpd": "httpd",
        "newrelic": "newrelic-infra"
    }
    
    for target, proc in process_map.items():
        if target in state.target_name.lower():
            process_name = proc
            break
    
    # Use target name as fallback
    if not process_name:
        process_name = state.target_name
    
    # Override with parameters if provided
    if state.parameters.get("process_name"):
        process_name = state.parameters.get("process_name")
    
    try:
        # Check with ps
        process = await asyncio.create_subprocess_exec(
            "ps", "-ef",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        output = stdout.decode()
        
        if re.search(rf"\b{re.escape(process_name)}\b", output):
            # Count instances
            instances = len(re.findall(rf"\b{re.escape(process_name)}\b", output))
            
            return {
                "success": True,
                "message": f"Process {process_name} is running ({instances} instances)",
                "process": process_name,
                "instances": instances
            }
        else:
            return {
                "success": False,
                "message": f"Process {process_name} is not running",
                "process": process_name,
                "instances": 0
            }
    except Exception as e:
        logger.error(f"Error checking process: {e}")
        return {
            "success": False,
            "message": f"Error checking process: {str(e)}",
            "process": process_name
        }

async def api_check_strategy(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check if an API is responding.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with verification results
    """
    # Determine which API to check based on integration type
    if "aws" in state.integration_type or "aws" in state.target_name:
        return await _aws_api_check(state, config)
    elif "azure" in state.integration_type or "azure" in state.target_name:
        return await _azure_api_check(state, config)
    elif "gcp" in state.integration_type or "gcp" in state.target_name:
        return await _gcp_api_check(state, config)
    elif "newrelic" in state.integration_type or "newrelic" in state.target_name:
        return await _newrelic_api_check(state, config)
    else:
        return {
            "success": False,
            "message": f"No API check implementation for {state.integration_type}",
            "integration": state.integration_type
        }

async def _aws_api_check(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check AWS API credentials and connectivity.
    
    Args:
        state: Current workflow state
        config: Optional configuration
        
    Returns:
        Dict with verification results
    """
    try:
        # Create environment variables with AWS credentials
        env = os.environ.copy()
        if state.parameters.get("aws_access_key"):
            env["AWS_ACCESS_KEY_ID"] = state.parameters.get("aws_access_key")
        
        if state.parameters.get("aws_secret_key"):
            env["AWS_SECRET_ACCESS_KEY"] = state.parameters.get("aws_secret_key")
        
        if state.parameters.get("aws_region"):
            env["AWS_DEFAULT_REGION"] = state.parameters.get("aws_region")
        
        # Run AWS CLI command to validate credentials
        process = await asyncio.create_subprocess_exec(
            "aws", "sts", "get-caller-identity",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Parse output
            try:
                identity = json.loads(stdout.decode())
                account_id = identity.get("Account")
                user_id = identity.get("UserId")
                
                return {
                    "success": True,
                    "message": f"AWS credentials valid for account {account_id}",
                    "account_id": account_id,
                    "user_id": user_id
                }
            except:
                return {
                    "success": True,
                    "message": "AWS credentials valid",
                    "output": stdout.decode()
                }
        else:
            return {
                "success": False,
                "message": f"AWS credentials invalid: {stderr.decode()}",
                "error": stderr.decode()
            }
    except Exception as e:
        logger.error(f"Error checking AWS API: {e}")
        return {
            "success": False,
            "message": f"Error checking AWS API: {str(e)}"
        }

async def _azure_api_check(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Check Azure API credentials and connectivity."""
    try:
        # Create environment variables with Azure credentials
        env = os.environ.copy()
        if state.parameters.get("tenant_id"):
            env["AZURE_TENANT_ID"] = state.parameters.get("tenant_id")
        
        if state.parameters.get("client_id"):
            env["AZURE_CLIENT_ID"] = state.parameters.get("client_id")
        
        if state.parameters.get("client_secret"):
            env["AZURE_CLIENT_SECRET"] = state.parameters.get("client_secret")
        
        # Run Azure CLI command to validate credentials
        process = await asyncio.create_subprocess_exec(
            "az", "account", "show",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Parse output
            try:
                account = json.loads(stdout.decode())
                tenant_id = account.get("tenantId")
                subscription_id = account.get("id")
                
                return {
                    "success": True,
                    "message": f"Azure credentials valid for tenant {tenant_id}",
                    "tenant_id": tenant_id,
                    "subscription_id": subscription_id
                }
            except:
                return {
                    "success": True,
                    "message": "Azure credentials valid",
                    "output": stdout.decode()
                }
        else:
            return {
                "success": False,
                "message": f"Azure credentials invalid: {stderr.decode()}",
                "error": stderr.decode()
            }
    except Exception as e:
        logger.error(f"Error checking Azure API: {e}")
        return {
            "success": False,
            "message": f"Error checking Azure API: {str(e)}"
        }

async def _gcp_api_check(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Check GCP API credentials and connectivity."""
    try:
        # Create temporary credentials file
        temp_dir = tempfile.mkdtemp(prefix='workflow-gcp-')
        creds_path = os.path.join(temp_dir, "credentials.json")
        
        if state.parameters.get("credentials"):
            with open(creds_path, 'w') as f:
                f.write(state.parameters.get("credentials"))
        
        # Create environment variables with GCP credentials
        env = os.environ.copy()
        env["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        
        # Run GCP CLI command to validate credentials
        process = await asyncio.create_subprocess_exec(
            "gcloud", "auth", "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {
                "success": True,
                "message": "GCP credentials valid",
                "output": stdout.decode()
            }
        else:
            return {
                "success": False,
                "message": f"GCP credentials invalid: {stderr.decode()}",
                "error": stderr.decode()
            }
    except Exception as e:
        logger.error(f"Error checking GCP API: {e}")
        return {
            "success": False,
            "message": f"Error checking GCP API: {str(e)}"
        }
    finally:
        # Cleanup
        try:
            if os.path.exists(creds_path):
                os.unlink(creds_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up GCP credentials: {e}")

async def _newrelic_api_check(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Check New Relic API credentials and connectivity."""
    license_key = state.parameters.get("license_key")
    api_key = state.parameters.get("api_key")
    
    if not license_key and not api_key:
        return {
            "success": False,
            "message": "Missing New Relic license_key or api_key"
        }
    
    # Try license key validation
    if license_key:
        try:
            url = "https://insights-collector.newrelic.com/v1/accounts/unknown/events"
            headers = {
                "Content-Type": "application/json",
                "X-Insert-Key": license_key
            }
            data = json.dumps([{"eventType": "WorkflowTest", "test": True}])
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "New Relic license key valid",
                            "response": await response.text()
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"New Relic license key invalid: {response.status}",
                            "status": response.status,
                            "response": await response.text()
                        }
        except Exception as e:
            logger.error(f"Error checking New Relic license key: {e}")
            return {
                "success": False,
                "message": f"Error checking New Relic license key: {str(e)}"
            }
    
    # Try API key validation
    if api_key:
        try:
            url = "https://api.newrelic.com/v2/applications.json"
            headers = {
                "X-Api-Key": api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "New Relic API key valid",
                            "response": await response.text()
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"New Relic API key invalid: {response.status}",
                            "status": response.status,
                            "response": await response.text()
                        }
        except Exception as e:
            logger.error(f"Error checking New Relic API key: {e}")
            return {
                "success": False,
                "message": f"Error checking New Relic API key: {str(e)}"
            }

# Register strategies
register_verification_strategy(SERVICE_CHECK, service_check_strategy)
register_verification_strategy(HTTP_CHECK, http_check_strategy)
register_verification_strategy(LOG_CHECK, log_check_strategy)
register_verification_strategy(PROCESS_CHECK, process_check_strategy)
register_verification_strategy(API_CHECK, api_check_strategy) 