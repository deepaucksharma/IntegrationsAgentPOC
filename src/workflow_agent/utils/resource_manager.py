"""Resource management for workflow agent."""
import os
import shutil
import asyncio
import logging
import aiofiles
import tempfile
from pathlib import Path
from typing import Dict, Set, Optional, Any, List
from contextlib import asynccontextmanager
from ..error.exceptions import ResourceError, ErrorContext

logger = logging.getLogger(__name__)

class ResourceManager:
    """Manages resources and ensures proper cleanup."""
    
    def __init__(self):
        self._temp_dirs: Set[str] = set()
        self._temp_files: Set[str] = set()
        self._active_processes: Dict[int, asyncio.subprocess.Process] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._cleanup_tasks: List[asyncio.Task] = []
        self._global_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the resource manager."""
        pass

    async def cleanup(self) -> None:
        """Clean up all resources."""
        try:
            async with self._global_lock:
                # Cancel all cleanup tasks
                for task in self._cleanup_tasks:
                    if not task.done():
                        task.cancel()
                
                # Wait for tasks to complete
                if self._cleanup_tasks:
                    await asyncio.gather(*self._cleanup_tasks, return_exceptions=True)
                
                # Clean up processes
                await self._cleanup_processes()
                
                # Clean up temporary files and directories
                await self._cleanup_temp_resources()
                
                # Clear all internal state
                self._temp_dirs.clear()
                self._temp_files.clear()
                self._active_processes.clear()
                self._locks.clear()
                self._semaphores.clear()
                self._cleanup_tasks.clear()
            
        except Exception as e:
            context = ErrorContext(component="ResourceManager", operation="cleanup")
            raise ResourceError("Failed to clean up resources", context=context, details={"error": str(e)})

    @asynccontextmanager
    async def managed_lock(self, name: str):
        """Context manager for safely managing locks."""
        lock = await self.get_lock(name)
        try:
            await lock.acquire()
            yield lock
        finally:
            lock.release()

    @asynccontextmanager
    async def managed_semaphore(self, name: str, value: int = 1):
        """Context manager for safely managing semaphores."""
        semaphore = await self.get_semaphore(name, value)
        try:
            await semaphore.acquire()
            yield semaphore
        finally:
            semaphore.release()

    @asynccontextmanager
    async def temp_file(self, suffix: Optional[str] = None, content: Optional[str] = None) -> str:
        """Create and manage a temporary file."""
        try:
            fd, path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            self._temp_files.add(path)
            
            if content is not None:
                async with aiofiles.open(path, mode='w') as f:
                    await f.write(content)
            
            yield path
        finally:
            if path in self._temp_files:
                try:
                    os.unlink(path)
                    self._temp_files.remove(path)
                except OSError as e:
                    logger.warning(f"Failed to remove temporary file {path}: {e}")

    @asynccontextmanager
    async def temp_dir(self) -> str:
        """Create and manage a temporary directory."""
        path = tempfile.mkdtemp()
        self._temp_dirs.add(path)
        try:
            yield path
        finally:
            if path in self._temp_dirs:
                try:
                    shutil.rmtree(path)
                    self._temp_dirs.remove(path)
                except OSError as e:
                    logger.warning(f"Failed to remove temporary directory {path}: {e}")

    async def get_lock(self, name: str) -> asyncio.Lock:
        """Get or create a named lock."""
        async with self._global_lock:
            if name not in self._locks:
                self._locks[name] = asyncio.Lock()
            return self._locks[name]

    async def get_semaphore(self, name: str, value: int = 1) -> asyncio.Semaphore:
        """Get or create a named semaphore."""
        async with self._global_lock:
            if name not in self._semaphores:
                self._semaphores[name] = asyncio.Semaphore(value)
            return self._semaphores[name]

    async def _cleanup_processes(self) -> None:
        """Clean up all active processes."""
        async with self._global_lock:
            for pid, process in list(self._active_processes.items()):
                try:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                except ProcessLookupError:
                    pass  # Process already terminated
                except Exception as e:
                    logger.error(f"Error terminating process {pid}: {e}")
                finally:
                    self._active_processes.pop(pid, None)

    async def _cleanup_temp_resources(self) -> None:
        """Clean up temporary files and directories."""
        # Clean up files
        for path in list(self._temp_files):
            try:
                os.unlink(path)
                self._temp_files.remove(path)
            except OSError as e:
                logger.warning(f"Failed to remove temporary file {path}: {e}")

        # Clean up directories
        for path in list(self._temp_dirs):
            try:
                shutil.rmtree(path)
                self._temp_dirs.remove(path)
            except OSError as e:
                logger.warning(f"Failed to remove temporary directory {path}: {e}")

    async def read_file_async(self, path: str) -> str:
        """Read file contents asynchronously."""
        async with aiofiles.open(path, mode='r') as f:
            return await f.read()

    async def write_file_async(self, path: str, content: str) -> None:
        """Write content to file asynchronously."""
        async with aiofiles.open(path, mode='w') as f:
            await f.write(content)

    async def copy_file_async(self, src: str, dst: str) -> None:
        """Copy file asynchronously."""
        async with aiofiles.open(src, mode='rb') as fsrc:
            async with aiofiles.open(dst, mode='wb') as fdst:
                await fdst.write(await fsrc.read())

    async def create_process(self, cmd: str, **kwargs) -> asyncio.subprocess.Process:
        """Create and track a subprocess."""
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs
        )
        self._active_processes[process.pid] = process
        
        # Create cleanup task
        cleanup_task = asyncio.create_task(self._monitor_process(process))
        self._cleanup_tasks.append(cleanup_task)
        
        return process

    async def _monitor_process(self, process: asyncio.subprocess.Process) -> None:
        """Monitor a process and clean up when it terminates."""
        try:
            await process.wait()
        except Exception as e:
            logger.error(f"Error monitoring process {process.pid}: {e}")
        finally:
            self._active_processes.pop(process.pid, None)

    def get_resource_stats(self) -> Dict[str, Any]:
        """Get current resource usage statistics."""
        return {
            "temp_directories": len(self._temp_dirs),
            "temp_files": len(self._temp_files),
            "active_processes": len(self._active_processes),
            "locks": len(self._locks),
            "semaphores": len(self._semaphores),
            "cleanup_tasks": len(self._cleanup_tasks)
        } 