"""Main entry point for workflow agent."""
import os
import sys
import asyncio
import logging
import signal
from typing import Dict, Any, Optional

from .agent import WorkflowAgent
from .utils.logging import setup_logging
from .config.loader import load_config_file, find_default_config

async def main():
    """Main entry point for direct agent execution."""
    setup_logging(log_level=os.environ.get("LOG_LEVEL", "INFO"))
    logger = logging.getLogger("workflow-agent")
    
    logger.info("Starting workflow agent")
    
    config_path = os.environ.get("WORKFLOW_CONFIG_PATH")
    if not config_path:
        config_path = find_default_config()
    
    if config_path:
        logger.info(f"Loading configuration from {config_path}")
        try:
            config = load_config_file(config_path)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    else:
        logger.info("No configuration file found, using defaults")
        config = {}
    
    agent = WorkflowAgent()
    
    try:
        logger.info("Initializing agent")
        await agent.initialize(config)
        logger.info("Agent initialized and running")
        stop_event = asyncio.Event()
        
        def signal_handler():
            logger.info("Stopping agent")
            stop_event.set()
        
        try:
            loop = asyncio.get_event_loop()
            for signame in ('SIGINT', 'SIGTERM'):
                try:
                    loop.add_signal_handler(getattr(signal, signame), signal_handler)
                except (NotImplementedError, AttributeError):
                    pass
            await stop_event.wait()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        
    except Exception as e:
        logger.exception(f"Error starting agent: {e}")
        sys.exit(1)
    finally:
        logger.info("Cleaning up resources")
        await agent.cleanup()
        logger.info("Agent stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(0)