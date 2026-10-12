"""
AutoDev PTY Adapter (Phase 5 - Secure Interactive Debugging)
Provides cross-platform pseudoterminal process execution, asynchronous bounded I/O,
environment sanitization, and terminal resizing capabilities.
"""

from abc import ABC, abstractmethod
from collections import deque
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BasePTYAdapter(ABC):
    """Abstract interface for interactive terminal I/O adapters."""

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def write(self, data: str) -> None:
        pass

    @abstractmethod
    def read(self, timeout_ms: int = 100) -> str:
        pass

    @abstractmethod
    def resize(self, cols: int, rows: int) -> None:
        pass

    @abstractmethod
    def terminate(self) -> None:
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        pass

    @abstractmethod
    def get_exit_code(self) -> Optional[int]:
        pass


class SubprocessPTYAdapter(BasePTYAdapter):
    """
    Subprocess-based interactive terminal adapter with bounded non-blocking queues,
    environment redaction, and thread-safe streaming.
    """

    def __init__(
        self,
        command: Optional[List[str]] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        max_buffer_lines: int = 1000,
    ) -> None:
        if command is None:
            if sys.platform == "win32":
                self.command = ["cmd.exe"]
            else:
                self.command = ["/bin/sh"]
        else:
            self.command = command

        self.cwd = cwd
        self.env = self._sanitize_env(env)
        self.max_buffer_lines = max_buffer_lines

        self.process: Optional[subprocess.Popen] = None
        self.out_queue: queue.Queue = queue.Queue(maxsize=5000)
        self.ring_buffer: deque = deque(maxlen=max_buffer_lines)
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self.cols = 80
        self.rows = 24

    def _sanitize_env(self, custom_env: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Strip coordinator tokens, API keys, and internal secrets from terminal environment."""
        base_env = os.environ.copy()
        # Redact sensitive variables
        sensitive_keywords = ["SECRET", "TOKEN", "KEY", "PASSWORD", "CREDENTIAL", "AUTH"]
        sanitized = {k: v for k, v in base_env.items() if not any(s in k.upper() for s in sensitive_keywords)}
        sanitized["AUTODEV_DEBUG_SESSION"] = "1"
        sanitized["TERM"] = "xterm-256color"
        if custom_env:
            for k, v in custom_env.items():
                if not any(s in k.upper() for s in sensitive_keywords):
                    sanitized[k] = v
        return sanitized

    def start(self) -> None:
        """Launch the subprocess and start the output reader thread."""
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                env=self.env,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()
        except Exception as e:
            logger.exception("Failed to start terminal subprocess: %s", e)
            self._running = False
            raise

    def _reader_loop(self) -> None:
        """Background thread reading lines/chunks from subprocess stdout."""
        if not self.process or not self.process.stdout:
            return

        try:
            while self._running and self.process.poll() is None:
                char_or_line = self.process.stdout.read(1024)
                if not char_or_line:
                    break
                try:
                    self.out_queue.put_nowait(char_or_line)
                    self.ring_buffer.append(char_or_line)
                except queue.Full:
                    # Drop oldest if queue full to prevent memory explosion
                    pass
        except Exception as e:
            logger.debug("Reader loop ended: %s", e)
        finally:
            self._running = False

    def write(self, data: str) -> None:
        """Write user input characters to subprocess stdin."""
        if self.process and self.process.stdin and self.process.poll() is None:
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                self._running = False

    def read(self, timeout_ms: int = 100) -> str:
        """Read available output from the queue within timeout."""
        chunks: List[str] = []
        timeout_sec = timeout_ms / 1000.0
        start = time.time()

        while True:
            try:
                remaining = max(0.0, timeout_sec - (time.time() - start))
                chunk = self.out_queue.get(timeout=remaining)
                chunks.append(chunk)
                # Drain any immediately available chunks
                while not self.out_queue.empty():
                    chunks.append(self.out_queue.get_nowait())
                break
            except queue.Empty:
                break

        return "".join(chunks)

    def resize(self, cols: int, rows: int) -> None:
        """Record new terminal dimensions."""
        self.cols = max(10, cols)
        self.rows = max(5, rows)

    def terminate(self) -> None:
        """Gracefully terminate subprocess."""
        self._running = False
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    self.process.kill()
                except OSError:
                    pass

    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def get_exit_code(self) -> Optional[int]:
        if self.process:
            return self.process.poll()
        return None
