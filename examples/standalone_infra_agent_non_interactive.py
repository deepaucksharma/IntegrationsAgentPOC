"""
DEPRECATED: Use standalone_infra_agent.py with the --non-interactive flag instead.

This script is kept for backward compatibility but will be removed in a future version.
"""
import sys
import os
import logging
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Forward to the new consolidated script with non-interactive flag."""
    logger.warning("This script is deprecated. Please use standalone_infra_agent.py with --non-interactive flag.")
    
    # Determine the action from command line args
    action = sys.argv[1] if len(sys.argv) > 1 else 'install'
    
    # Import the new script and run it with non-interactive flag
    try:
        from standalone_infra_agent import main as new_main
        
        # Set sys.argv to pass the appropriate arguments
        sys.argv = ['standalone_infra_agent.py', '--non-interactive', f'--action={action}']
        if len(sys.argv) > 2:  # If license key was provided
            sys.argv.append(f'--license={sys.argv[2]}')
            
        return await new_main()
    except Exception as e:
        logger.error(f"Error forwarding to new script: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
