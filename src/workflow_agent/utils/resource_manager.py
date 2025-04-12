"""
Resource management for workflow agent.
Provides centralized management of temporary files, processes, and synchronization primitives.
Integrates with ChangeTracker for standardized change tracking.
"""
import os
import shutil
import asyncio
import logging
import aiofiles
import tempfile
from pathlib import Path
from typing import Dict, Set, Optional, Any, List, Union
from contextlib import asynccontextmanager
from ..error.exceptions import ResourceError, ErrorContext
from ..core.state import Change

logger = logging.getLogger(__name__)

class ResourceManager:
    """
    Manages resources and ensures proper cleanup.
    Handles temporary files, directories, processes, locks, and semaphores.
    """
    
    def __init__(self, config=None):
        """
        Initialize the resource manager with empty collections.
        
        Args:
            config: Optional configuration object
        """
        self._temp_dirs: Set[str] = set()
        self._temp_files: Set[str] = set()
        self._active_processes: Dict[int, asyncio.subprocess.Process] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._cleanup_tasks: List[asyncio.Task] = []
        self._global_lock = asyncio.Lock()
        self._config = config
        
        # Initialize the change tracker
        self._create_change_tracker()

    async def initialize(self) -> None:
        """Initialize the resource manager."""
        logger.debug("ResourceManager initialized")

    async def cleanup(self) -> None:
        """
        Clean up all managed resources in a safe and orderly manner.
        Order: Tasks -> Processes -> Temp Files -> Temp Directories
        """
        try:
            logger.info("Starting ResourceManager cleanup...")
            
            # Get resource counts for logging
            resource_stats = self.get_resource_stats()
            logger.info(
                "Resources to clean up: %d tasks, %d processes, %d files, %d directories",
                resource_stats["cleanup_tasks"],
                resource_stats["active_processes"],
                resource_stats["temp_files"],
                resource_stats["temp_directories"]
            )
            
            # Step 1: Perform cleanup operations with global lock protection
            async with self._global_lock:
                # Cancel all cleanup tasks first
                await self._cleanup_all_tasks()
            
            # Step 2: Clean up all resources
            await self._cleanup_all_resources()
            
            # Step 3: Clear internal state
            self._clear_internal_state()
            
            logger.info("ResourceManager cleanup completed successfully")
        
        except Exception as e:
            context = ErrorContext(component="ResourceManager", operation="cleanup")
            logger.error("Failed to clean up resources: %s", str(e), exc_info=True)
            raise ResourceError("Failed to clean up resources", context=context, details={"error": str(e)})

    async def _cleanup_all_tasks(self) -> None:
        """Cancel and wait for all cleanup tasks to complete."""
        if self._cleanup_tasks:
            logger.debug("Cancelling %d cleanup tasks...", len(self._cleanup_tasks))
            for task in self._cleanup_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            logger.debug("Waiting for cleanup tasks to complete...")
            await asyncio.gather(*self._cleanup_tasks, return_exceptions=True)
            logger.debug("All cleanup tasks completed")

    async def _cleanup_all_resources(self) -> None:
        """Clean up all types of resources in a consolidated approach."""
        # Step 1: Clean up processes
        if self._active_processes:
            logger.info("Cleaning up %d active processes...", len(self._active_processes))
            await self._terminate_processes()
        
        # Step 2: Clean up all temporary resources in one pass
        await self._remove_temp_resources()

    def _clear_internal_state(self) -> None:
        """Clear all internal state after cleanup."""
        self._temp_dirs.clear()
        self._temp_files.clear()
        self._active_processes.clear()
        self._locks.clear()
        self._semaphores.clear()
        self._cleanup_tasks.clear()
        logger.debug("All internal state cleared")

    @asynccontextmanager
    async def managed_lock(self, name: str):
        """
        Context manager for safely managing locks.
        
        Args:
            name: Lock identifier
            
        Yields:
            The lock object
        """
        lock = await self.get_lock(name)
        try:
            await lock.acquire()
            yield lock
        finally:
            lock.release()

    @asynccontextmanager
    async def managed_semaphore(self, name: str, value: int = 1):
        """
        Context manager for safely managing semaphores.
        
        Args:
            name: Semaphore identifier
            value: Max concurrent access
            
        Yields:
            The semaphore object
        """
        semaphore = await self.get_semaphore(name, value)
        try:
            await semaphore.acquire()
            yield semaphore
        finally:
            semaphore.release()

    @asynccontextmanager
    async def temp_file(self, suffix: Optional[str] = None, content: Optional[str] = None) -> str:
        """
        Create and manage a temporary file.
        
        Args:
            suffix: Optional file extension
            content: Optional content to write to the file
            
        Yields:
            Path to the temporary file
        """
        try:
            fd, path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            self._temp_files.add(path)
            logger.debug("Created temporary file: %s", path)
            
            if content is not None:
                logger.debug("Writing content to temporary file: %s", path)
                async with aiofiles.open(path, mode='w') as f:
                    await f.write(content)
            
            yield path
        finally:
            if path in self._temp_files:
                try:
                    logger.debug("Removing temporary file: %s", path)
                    os.unlink(path)
                    self._temp_files.remove(path)
                except OSError as e:
                    logger.warning("Failed to remove temporary file %s: %s", path, e)

    @asynccontextmanager
    async def temp_dir(self) -> str:
        """
        Create and manage a temporary directory.
        
        Yields:
            Path to the temporary directory
        """
        path = tempfile.mkdtemp()
        self._temp_dirs.add(path)
        logger.debug("Created temporary directory: %s", path)
        try:
            yield path
        finally:
            if path in self._temp_dirs:
                try:
                    logger.debug("Removing temporary directory: %s", path)
                    shutil.rmtree(path)
                    self._temp_dirs.remove(path)
                except OSError as e:
                    logger.warning("Failed to remove temporary directory %s: %s", path, e)

    async def get_lock(self, name: str) -> asyncio.Lock:
        """
        Get or create a named lock.
        
        Args:
            name: Lock identifier
            
        Returns:
            The lock object
        """
        async with self._global_lock:
            if name not in self._locks:
                self._locks[name] = asyncio.Lock()
            return self._locks[name]

    async def get_semaphore(self, name: str, value: int = 1) -> asyncio.Semaphore:
        """
        Get or create a named semaphore.
        
        Args:
            name: Semaphore identifier
            value: Max concurrent access
            
        Returns:
            The semaphore object
        """
        async with self._global_lock:
            if name not in self._semaphores:
                self._semaphores[name] = asyncio.Semaphore(value)
            return self._semaphores[name]

    async def _terminate_processes(self) -> None:
        """
        Terminate all active processes with graceful fallback to killing.
        Protected by the global lock to avoid race conditions.
        """
        async with self._global_lock:
            for pid, process in list(self._active_processes.items()):
                try:
                    logger.debug("Terminating process %d...", pid)
                    process.terminate()
                    
                    # Wait for termination with timeout
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                        logger.debug("Process %d terminated gracefully", pid)
                    except asyncio.TimeoutError:
                        # Force kill if termination times out
                        logger.warning("Process %d did not terminate, forcing kill", pid)
                        process.kill()
                        await process.wait()
                        logger.debug("Process %d killed", pid)
                except ProcessLookupError:
                    logger.debug("Process %d already terminated", pid)
                except Exception as e:
                    logger.error("Error terminating process %d: %s", pid, e)
                finally:
                    # Always remove from tracking
                    self._active_processes.pop(pid, None)
            
            logger.info("All processes have been terminated")

    async def _remove_temp_resources(self) -> None:
        """
        Remove all temporary files and directories in one consolidated operation.
        """
        # Process files and directories counts
        files_count = len(self._temp_files)
        dirs_count = len(self._temp_dirs)
        
        if files_count == 0 and dirs_count == 0:
            logger.debug("No temporary resources to clean up")
            return
            
        logger.info("Removing temporary resources: %d files, %d directories", files_count, dirs_count)
        
        # Remove files first
        removed_files = 0
        for path in list(self._temp_files):
            try:
                os.unlink(path)
                self._temp_files.remove(path)
                removed_files += 1
            except OSError as e:
                logger.warning("Failed to remove temporary file %s: %s", path, e)

        # Then remove directories
        removed_dirs = 0
        for path in list(self._temp_dirs):
            try:
                shutil.rmtree(path)
                self._temp_dirs.remove(path)
                removed_dirs += 1
            except OSError as e:
                logger.warning("Failed to remove temporary directory %s: %s", path, e)
                
        logger.info("Removed %d/%d files and %d/%d directories", 
                   removed_files, files_count, 
                   removed_dirs, dirs_count)

    async def read_file_async(self, path: str) -> str:
        """
        Read file contents asynchronously.
        
        Args:
            path: Path to the file
            
        Returns:
            File content as string
        """
        logger.debug("Reading file asynchronously: %s", path)
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
            logger.debug("Successfully read %d bytes from file: %s", len(content), path)
            return content

    async def write_file_async(self, path: str, content: str) -> None:
        """
        Write content to file asynchronously.
        
        Args:
            path: Path to the file
            content: Content to write
        """
        logger.debug("Writing file asynchronously: %s", path)
        async with aiofiles.open(path, mode='w') as f:
            await f.write(content)
            logger.debug("Successfully wrote %d bytes to file: %s", len(content), path)

    async def copy_file_async(self, src: str, dst: str) -> None:
        """
        Copy file asynchronously.
        
        Args:
            src: Source file path
            dst: Destination file path
        """
        logger.debug("Copying file asynchronously from %s to %s", src, dst)
        async with aiofiles.open(src, mode='rb') as fsrc:
            async with aiofiles.open(dst, mode='wb') as fdst:
                content = await fsrc.read()
                await fdst.write(content)
                logger.debug("Successfully copied %d bytes from %s to %s", len(content), src, dst)

    async def create_process(self, cmd: str, **kwargs) -> asyncio.subprocess.Process:
        """
        Create and track a subprocess with monitoring.
        
        Args:
            cmd: Command to execute
            **kwargs: Additional arguments for subprocess creation
            
        Returns:
            Process object
        """
        logger.debug("Creating subprocess with command: %s", cmd)
        
        # Create the process
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs
        )
        
        # Track the process
        async with self._global_lock:
            self._active_processes[process.pid] = process
            
            # Create monitoring task
            cleanup_task = asyncio.create_task(self._monitor_process(process))
            self._cleanup_tasks.append(cleanup_task)
            
        logger.info("Created process with PID %d", process.pid)
        return process

    async def _monitor_process(self, process: asyncio.subprocess.Process) -> None:
        """
        Monitor a process and clean up when it terminates.
        
        Args:
            process: Process to monitor
        """
        try:
            # Wait for process to complete
            await process.wait()
            logger.info("Process %d terminated with return code %d", 
                       process.pid, process.returncode)
        except asyncio.CancelledError:
            logger.debug("Process monitoring for PID %d was cancelled", process.pid)
            raise
        except Exception as e:
            logger.error("Error monitoring process %d: %s", process.pid, e)
        finally:
            # Remove from active processes
            async with self._global_lock:
                self._active_processes.pop(process.pid, None)
                logger.debug("Removed process %d from active processes", process.pid)

    def _create_change_tracker(self):
        """Create an instance of the ChangeTracker for tracking script changes."""
        # Import here to avoid circular imports
        from ..execution.change_tracker import ChangeTracker
        self.change_tracker = ChangeTracker()
        logger.debug("ChangeTracker initialized")
    
    def track_changes(self, output: str) -> List[Change]:
        """
        Track changes from script output using the centralized ChangeTracker.
        
        Args:
            output: Script output to parse
            
        Returns:
            List of Change objects
        """
        logger.debug("Tracking changes from script output")
        return self.change_tracker.extract_changes(output)
    
    def register_change(self, change_type: str, target: str, revertible: bool = False, 
                      revert_command: Optional[str] = None, backup_file: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Change:
        """
        Manually register a change.
        
        Args:
            change_type: Type of change
            target: Target of the change
            revertible: Whether the change can be reverted
            revert_command: Command to revert the change
            backup_file: Path to backup file if any
            metadata: Additional metadata
            
        Returns:
            Created Change object
        """
        change = Change(
            type=change_type,
            target=target,
            revertible=revertible,
            revert_command=revert_command,
            backup_file=backup_file,
            metadata=metadata or {}
        )
        logger.debug(f"Manually registered change: {change_type} on {target}")
        return change
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """
        Get current resource usage statistics.
        
        Returns:
            Dictionary with resource counts
        """
        stats = {
            "temp_directories": len(self._temp_dirs),
            "temp_files": len(self._temp_files),
            "active_processes": len(self._active_processes),
            "locks": len(self._locks),
            "semaphores": len(self._semaphores),
            "cleanup_tasks": len(self._cleanup_tasks)
        }
        return stats
