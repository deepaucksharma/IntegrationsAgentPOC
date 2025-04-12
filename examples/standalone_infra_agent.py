"""
Standalone Infrastructure Agent Workflow Script

This script demonstrates a complete workflow for installing, verifying,
and uninstalling the New Relic Infrastructure Agent on Windows.

The implementation has been refactored into distinct components with clear
separation of concerns between template rendering, script execution, and
result processing.

Usage:
    python standalone_infra_agent.py [options]

Options:
    --action=ACTION    Specify action: install, verify, uninstall, or full (default: full)
    --non-interactive  Run in non-interactive mode
    --license=KEY      New Relic license key
"""
import os
import sys
import asyncio
import logging
import tempfile
import subprocess
import platform
import argparse
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Try to use the centralized config loader if available
try:
    from workflow_agent.config.loader import load_example_config
    USE_CENTRAL_CONFIG = True
except ImportError:
    USE_CENTRAL_CONFIG = False

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScriptRenderer:
    """Handles template loading and rendering."""
    
    def __init__(self, template_dir=None):
        """
        Initialize script renderer.
        
        Args:
            template_dir: Directory containing templates
        """
        self.project_root = Path(__file__).parent.parent
        self.template_dir = template_dir or self.project_root / 'templates'
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        logger.debug(f"ScriptRenderer initialized with template directory: {self.template_dir}")
    
    def render_script(self, action, context):
        """
        Render a script from a template.
        
        Args:
            action: Action to perform (install, verify, uninstall)
            context: Template context
            
        Returns:
            Tuple of (rendered script, template path)
        """
        template_file = f"{action}/infra_agent.ps1.j2"
        
        # Check if template exists
        if not (self.template_dir / template_file).exists() and not (self.template_dir / template_file.replace('.j2', '')).exists():
            logger.warning(f"Template not found: {template_file}")
            # Try fallback to default template
            template_file = f"{action}/default.ps1.j2" 
            if not (self.template_dir / template_file).exists() and not (self.template_dir / template_file.replace('.j2', '')).exists():
                logger.error(f"Fallback template not found: {template_file}")
                return None, template_file
        
        # Load and render template
        try:
            template = self.env.get_template(template_file)
            rendered = template.render(**context)
            logger.info(f"Successfully rendered template: {template_file}")
            return rendered, template_file
        except Exception as e:
            logger.error(f"Error rendering template: {e}", exc_info=True)
            return None, template_file

class ScriptExecutor:
    """Handles script execution."""
    
    def __init__(self):
        """Initialize script executor."""
        pass
    
    async def execute_script(self, script_content):
        """
        Execute a PowerShell script.
        
        Args:
            script_content: Script content to execute
            
        Returns:
            Tuple of (success, stdout, stderr, return_code)
        """
        if not script_content:
            logger.error("No script content provided for execution")
            return False, "", "No script content", 1
        
        # Write script to temporary file
        with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode='w') as temp:
            temp_path = temp.name
            temp.write(script_content)
            logger.info(f"Script written to temporary file: {temp_path}")
        
        # Execute script and collect results
        try:
            logger.info(f"Executing script: {temp_path}")
            cmd = f'powershell.exe -ExecutionPolicy Bypass -File "{temp_path}"'
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                shell=True,
                text=True
            )
            
            # Process output
            stdout, stderr = process.communicate()
            
            logger.info(f"Script execution complete with exit code: {process.returncode}")
            return (process.returncode == 0), stdout, stderr, process.returncode
                
        except Exception as e:
            logger.error(f"Error executing script: {e}", exc_info=True)
            return False, "", str(e), 1
        finally:
            # Clean up temporary script file
            try:
                os.unlink(temp_path)
                logger.debug(f"Removed temporary script: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary script: {e}")

class OutputProcessor:
    """Processes and displays execution results."""
    
    def __init__(self, non_interactive=False):
        """
        Initialize output processor.
        
        Args:
            non_interactive: Whether to run in non-interactive mode
        """
        self.non_interactive = non_interactive
    
    def process_result(self, action, success, stdout, stderr):
        """
        Process and display execution results.
        
        Args:
            action: Action performed
            success: Whether execution was successful
            stdout: Standard output
            stderr: Standard error
        """
        # Display output based on interactive mode
        if not self.non_interactive:
            print(f"\n{action.capitalize()} Script Output:")
            print("-" * 50)
            if stdout:
                print(stdout)
            else:
                print("No output")
            
            if stderr:
                print(f"\n{action.capitalize()} Script Errors:")
                print("-" * 50)
                print(stderr)
        else:
            # In non-interactive mode, just log the results
            if stdout:
                logger.info(f"{action.capitalize()} output: {stdout[:500]}...")
            if stderr:
                logger.warning(f"{action.capitalize()} errors: {stderr[:500]}...")
        
        # Log the result
        if success:
            logger.info(f"{action.capitalize()} executed successfully!")
        else:
            logger.error(f"{action.capitalize()} script execution failed.")
        
        return success

class WorkflowRunner:
    """Coordinates the workflow process."""
    
    def __init__(self, license_key=None, non_interactive=False):
        """
        Initialize workflow runner.
        
        Args:
            license_key: New Relic license key
            non_interactive: Whether to run in non-interactive mode
        """
        self.non_interactive = non_interactive
        
        # Initialize components
        self.renderer = ScriptRenderer()
        self.executor = ScriptExecutor()
        self.processor = OutputProcessor(non_interactive)
        
        # Load configuration
        if USE_CENTRAL_CONFIG:
            config = load_example_config(license_key=license_key)
            self.params = config["parameters"]
        else:
            # Define parameters directly
            self.params = {
                "license_key": license_key or os.environ.get("NEW_RELIC_LICENSE_KEY", "YOUR_LICENSE_KEY"),
                "host": "localhost",
                "port": "8080",
                "install_dir": r"C:\Program Files\New Relic",
                "config_path": r"C:\ProgramData\New Relic",
                "log_path": r"C:\ProgramData\New Relic\logs"
            }
        
        # Check if running on Windows
        if os.name != 'nt':
            logger.error("This script must be run on Windows.")
            sys.exit(1)
    
    async def run_workflow(self, action):
        """
        Run a workflow with the specified action (install, verify, uninstall).
        
        Args:
            action: Action to perform (install, verify, uninstall)
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Running {action} workflow...")
        
        # Create template context
        context = {
            'action': action,
            'target_name': 'infrastructure-agent',
            'integration_type': 'infra_agent',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': self.params
        }
        
        # Step 1: Render the script
        rendered_script, template_path = self.renderer.render_script(action, context)
        if not rendered_script:
            logger.error(f"Failed to render script for action: {action}")
            return False
        
        # Step 2: Execute the script
        success, stdout, stderr, return_code = await self.executor.execute_script(rendered_script)
        
        # Step 3: Process the results
        result = self.processor.process_result(action, success, stdout, stderr)
        
        return result
    
    async def run_full_workflow(self):
        """
        Run the complete workflow: install, verify, uninstall.
        
        Returns:
            True if successful, False otherwise
        """
        # Only show banner in interactive mode
        if not self.non_interactive:
            print("\n" + "=" * 60)
            print("INFRASTRUCTURE AGENT WORKFLOW DEMONSTRATION")
            print("=" * 60)
        
        # Install
        install_result = await self.run_workflow("install")
        if not install_result:
            logger.error("Installation failed, aborting workflow.")
            return False
        
        # Wait a moment for installation to complete
        await asyncio.sleep(2)
        
        # Verify
        verify_result = await self.run_workflow("verify")
        if not verify_result:
            logger.warning("Verification had issues, but continuing with workflow.")
        
        # Wait a moment before uninstalling
        await asyncio.sleep(2)
        
        # Uninstall
        uninstall_result = await self.run_workflow("uninstall")
        if not uninstall_result:
            logger.error("Uninstallation failed.")
            return False
        
        logger.info("Full workflow completed successfully!")
        return True

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="New Relic Infrastructure Agent Workflow")
    parser.add_argument("--action", choices=["install", "verify", "uninstall", "full"], 
                      default="full", help="Action to perform (default: full)")
    parser.add_argument("--non-interactive", action="store_true", 
                      help="Run in non-interactive mode")
    parser.add_argument("--license", help="New Relic license key")
    return parser.parse_args()

async def main():
    args = parse_args()
    
    # Create workflow runner
    runner = WorkflowRunner(
        license_key=args.license,
        non_interactive=args.non_interactive
    )
    
    if args.action == "full":
        result = await runner.run_full_workflow()
    else:
        result = await runner.run_workflow(args.action)
    
    # Exit with appropriate status code
    if result:
        logger.info(f"Workflow '{args.action}' completed successfully!")
        return 0
    else:
        logger.error(f"Workflow '{args.action}' failed!")
        return 1

if __name__ == "__main__":
    logger.info("Starting Infrastructure Agent workflow...")
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
