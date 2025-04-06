"""
Standalone Infrastructure Agent Workflow Script

This script demonstrates a complete workflow for installing, verifying,
and uninstalling the New Relic Infrastructure Agent on Windows.

It directly renders templates to avoid the issue with template_data variable
not being passed correctly in the main framework.
"""
import os
import sys
import asyncio
import logging
import tempfile
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkflowRunner:
    """Runner for infrastructure agent workflows."""
    
    def __init__(self, license_key=None):
        """Initialize workflow runner."""
        self.project_root = Path(__file__).parent.parent
        self.template_dir = self.project_root / 'templates'
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        
        # Define parameters
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
        """Run a workflow with the specified action (install, verify, uninstall)."""
        logger.info(f"Running {action} workflow...")
        
        template_file = f"{action}/infra_agent.ps1.j2"
        
        # Check if template exists
        if not (self.template_dir / template_file).exists() and not (self.template_dir / template_file.replace('.j2', '')).exists():
            logger.error(f"Template not found: {template_file}")
            # Try fallback to default template
            template_file = f"{action}/default.ps1.j2" 
            if not (self.template_dir / template_file).exists() and not (self.template_dir / template_file.replace('.j2', '')).exists():
                logger.error(f"Fallback template not found: {template_file}")
                return False
        
        # Create template context
        context = {
            'action': action,
            'target_name': 'infrastructure-agent',
            'integration_type': 'infra_agent',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': self.params
        }
        
        # Load and render template
        try:
            template = self.env.get_template(template_file)
            rendered = template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template: {str(e)}", exc_info=True)
            return False
        
        # Write rendered script to temp file
        try:
            with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode='w') as temp:
                temp_path = temp.name
                temp.write(rendered)
                logger.info(f"Rendered {action} script written to: {temp_path}")
        except Exception as e:
            logger.error(f"Error writing temp file: {str(e)}", exc_info=True)
            return False
        
        # Execute script
        logger.info(f"Executing {action} script...")
        try:
            cmd = f'powershell.exe -ExecutionPolicy Bypass -File "{temp_path}"'
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                shell=True,
                text=True
            )
            
            # Process output
            stdout, stderr = process.communicate(timeout=300)  # 5 minute timeout
            
            logger.info(f"{action.capitalize()} script execution complete.")
            logger.info(f"Exit code: {process.returncode}")
            
            if stdout:
                print(f"\n{action.capitalize()} Script Output:")
                print("-" * 50)
                print(stdout)
            
            if stderr:
                print(f"\n{action.capitalize()} Script Errors:")
                print("-" * 50)
                print(stderr)
                
            if process.returncode != 0:
                logger.error(f"{action.capitalize()} script execution failed.")
                return False
                
            logger.info(f"{action.capitalize()} script executed successfully!")
            return True
                
        except subprocess.TimeoutExpired:
            logger.error(f"{action.capitalize()} script execution timed out.")
            process.kill()
            return False
        except Exception as e:
            logger.error(f"Error executing {action} script: {str(e)}", exc_info=True)
            return False
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    async def run_complete_workflow(self):
        """Run the complete workflow: install, verify, uninstall."""
        logger.info("Starting complete infrastructure agent workflow...")
        
        # Try to install
        install_result = await self.run_workflow("install")
        if not install_result:
            logger.error("Installation failed!")
            return False
        
        # Try to verify
        verify_result = await self.run_workflow("verify")
        if not verify_result:
            logger.warning("Verification failed! Proceeding to uninstall...")
        else:
            logger.info("Verification successful!")
        
        # Always try to uninstall to clean up
        uninstall_result = await self.run_workflow("uninstall")
        if not uninstall_result:
            logger.error("Uninstallation failed!")
            return False
        
        logger.info("Uninstallation successful!")
        return True


async def main():
    """Main entry point."""
    # Get license key from command line or environment variable
    license_key = None
    if len(sys.argv) > 1:
        license_key = sys.argv[1]
    
    # Create and run workflow
    runner = WorkflowRunner(license_key)
    if len(sys.argv) > 2 and sys.argv[2] in ["install", "verify", "uninstall"]:
        # Run specific action
        action = sys.argv[2]
        result = await runner.run_workflow(action)
    else:
        # Run complete workflow
        result = await runner.run_complete_workflow()
    
    if result:
        logger.info("Workflow completed successfully!")
        return 0
    else:
        logger.error("Workflow failed!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
