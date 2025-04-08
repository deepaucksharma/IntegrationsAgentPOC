"""
infra_agent_uninstall.ps1.j2 script for infra_agent integration.
"""
import os
import sys
import asyncio
import logging
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def render_and_execute_template():
    """Render the template and execute it directly."""
    try:
        # Path to templates
        project_root = Path(__file__).parent
        template_dir = project_root / 'templates'
        env = Environment(loader=FileSystemLoader(template_dir))
        
        # Load template
        template = env.get_template('infra_agent_uninstall.ps1.j2')
        
        # Define parameters for the template
        params = {
            "license_key": os.environ.get('NR_LICENSE_KEY', 'YOUR_LICENSE_KEY'),
            "host": os.environ.get('NR_HOST', 'localhost'),
            "port": "8080",
            "install_dir": os.environ.get('NR_INSTALL_DIR', 'C:\\Program Files\\New Relic'),
            "config_path": os.environ.get('NR_CONFIG_PATH', 'C:\\ProgramData\\New Relic'),
            "log_path": os.environ.get('NR_LOG_PATH', 'C:\\ProgramData\\New Relic\\logs')
        }
        
        # Define template context
        context = {
            'action': 'uninstall',
            'target_name': 'infrastructure-agent',
            'integration_type': 'infra_agent',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': params
        }
        
        # Render the template
        logger.info("Rendering template...")
        rendered = template.render(**context)
        
        # Write the rendered script to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode='w') as temp:
            temp_path = temp.name
            temp.write(rendered)
            logger.info(f"Rendered script written to: {temp_path}")
        
        # Execute the script
        logger.info("Executing script...")
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
        
        logger.info("Script execution complete.")
        logger.info(f"Exit code: {process.returncode}")
        
        if stdout:
            print("\nScript Output:")
            print("-" * 50)
            print(stdout)
        
        if stderr:
            print("\nScript Errors:")
            print("-" * 50)
            print(stderr)
            
        if process.returncode != 0:
            logger.error("Script execution failed.")
            return False
        
        logger.info("Script executed successfully!")
        return True
            
    except Exception as e:
        logger.error(f"Error during execution: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # Check if running on Windows
    if os.name != 'nt':
        logger.error("This script must be run on Windows.")
        sys.exit(1)
        
    logger.info("Starting workflow execution...")
    result = asyncio.run(render_and_execute_template())
    
    if result:
        logger.info("Workflow completed successfully!")
        sys.exit(0)
    else:
        logger.error("Workflow failed!")
        sys.exit(1)
