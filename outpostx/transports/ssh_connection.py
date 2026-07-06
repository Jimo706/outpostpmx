"""
ssh_connection.py — SSH transport for OpTermx (Paramiko) using a blocking reader thread.

Responsibilities:
- Establish an SSH connection and interactive shell channel
- Spawn/stop a background reader thread that forwards output to the adapter
- Provide a simple send() API that writes user keystrokes/lines to the channel
- Optionally adjust remote PTY size on POSIX when the local terminal resizes

Notes:
- Designed to match the blocking-thread pattern used by Serial/TCP/AGWPE for consistency.
- Inbound/outbound text is UTF-8; undecodable bytes are replaced.
"""

from __future__ import annotations

import sys
import time
import platform
import threading
import struct
import signal
from typing import Callable, Optional

import paramiko

from .connection_base import BaseConnection
from .exceptions import SSHConnectionError, SSHResizeError, SSHReadError  # keep your existing types

IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    # No SIGWINCH; terminal raw mode not used on Windows here
    pass
else:
    import termios, tty, fcntl  # type: ignore[import-not-found]


class SSHConnection(BaseConnection):
    """Interactive SSH shell with a background reader thread.

    Args:
        host: SSH server hostname or IP.
        port: SSH port (default 22).
        username: SSH username.
        password: SSH password (key auth can be added later).
        term: Remote terminal type to request (default 'xterm').
        cols: Initial PTY width (characters).
        rows: Initial PTY height (characters).

    Threading:
        - Reader thread continually drains the channel and emits text to the adapter.
        - disconnect() stops the loop, closes resources, and joins the thread.

    Adapter callback:
        - Call register_adapter_callback(cb) where cb(str) receives text/status lines.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        term: str = "xterm",
        cols: int = 80,
        rows: int = 24,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.term = term
        self.cols = cols
        self.rows = rows

        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None

        self.read_thread: Optional[threading.Thread] = None
        self.running = False
        self.is_connected = False

        # POSIX stdin state (only when in a real TTY)
        self._old_stdin_mode = None

        self._send_to_adapter: Optional[Callable[[str], None]] = None

    # ---------------- Adapter wiring ----------------

    def register_adapter_callback(self, cb: Callable[[str], None]) -> None:
        """Register the adapter callback to receive UI text and status lines."""
        self._send_to_adapter = cb

    def _emit(self, text: str) -> None:
        """Safely emit text to the adapter if present."""
        if self._send_to_adapter:
            self._send_to_adapter(text)

    # ---------------- Lifecycle ---------------------

    def connect(self) -> bool:
        """Open SSH connection, start shell channel, and launch the reader thread.

        Returns:
            True on success; False if the connection fails (an error line is emitted).
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                look_for_keys=True,
                allow_agent=True,
                timeout=5.0,
            )

            # Request an interactive shell with PTY
            self.channel = self.client.invoke_shell(term=self.term, width=self.cols, height=self.rows)
            self.channel.settimeout(0.0)  # non-blocking for recv_ready()+recv()

            self.channel.send(
                "stty -echo; "
                "unset PROMPT_COMMAND; "                   # stop terminal-title OSC spam
                "export TERM=vt100; "                      # simple termcap → fewer colors
                "bind 'set enable-bracketed-paste off'; "  # kill 2004h/l prompts
                "alias ls='ls --color=never'; "            # no color codes
                "export PS1='\\u@\\h:\\w\\$ ' ; "          # simple prompt (no color escapes)
                "stty echo; "
                "\r\n"
                )

            # POSIX: set up SIGWINCH to resize remote PTY; CLI-only (TTY)
            if not IS_WINDOWS and sys.stdout.isatty():
                try:
                    signal.signal(signal.SIGWINCH, self._handle_resize)  # best effort
                    self._handle_resize()  # initial size sync
                except Exception:
                    # Non-fatal: some environments disallow setting signals
                    pass

            self.running = True
            self.is_connected = True
            self._emit(f"[Connected] SSH shell to {self.username}@{self.host}:{self.port}\n")

            # Reader thread
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True, name="SshReadLoop")
            self.read_thread.start()

            """
            removed the same POSIX tty.setraw() / termios stdin mode code.
            # POSIX: set stdin raw only for real TTY (CLI case, not GUI)
            if not IS_WINDOWS and sys.stdin.isatty():
                fd = sys.stdin.fileno()
                self._old_stdin_mode = termios.tcgetattr(fd)
                tty.setraw(fd)
            """

            return True

        except Exception as e:
            # Report to UI and return False (keep exception types for future if you want to raise instead)
            self.is_connected = False
            self._emit(f"[SSH Connect Error] {e}\n")
            return False

    def disconnect(self) -> None:
        """Stop the reader, restore terminal (POSIX), and close SSH resources."""
        self.running = False

        # POSIX: restore stdin if we changed it
        if not IS_WINDOWS and self._old_stdin_mode and sys.stdin.isatty():
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_stdin_mode)
            except Exception:
                pass
            finally:
                self._old_stdin_mode = None

        # Close channel/client
        try:
            if self.channel:
                self.channel.close()
        except Exception:
            pass
        finally:
            self.channel = None

        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        finally:
            self.client = None

        # Join reader
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.5)

        self.is_connected = False
        self._emit("[Disconnected] SSH\n")

    # ---------------- I/O ---------------------------

    def send(self, data: str) -> None:
        """Send text to the remote shell channel (no newline auto-added).

        The GUI typically appends CR/LF based on user actions;
        here we send exactly what we're given.

        Raises:
            SSHConnectionError: if the channel is not open.
        """
        if not (self.channel and not self.channel.closed):
            raise SSHConnectionError("SSH channel is not open")
            return

        try:
            # Paramiko accepts str (it encodes) or bytes; be explicit:
            self.channel.send(data.encode("utf-8", errors="replace"))
        except Exception as e:
            # Surface error to UI; caller can catch if needed
            self._emit(f"[SSH Write Error] {e}\n")
            raise
            return

    def receive(self) -> str:
        """Satisfy BaseConnection interface; unused (async via reader thread)."""
        return ""

    # ---------------- Internals ---------------------

    def _read_loop(self) -> None:
        """Continuously read from the SSH channel and emit decoded text."""
        try:
            while self.running and self.channel and not self.channel.closed:
                try:
                    if self.channel.recv_ready():
                        indata = self.channel.recv(4096)
                        if not indata:
                            break
                        self._emit(indata.decode("utf-8", errors="replace"))
                    else:
                        time.sleep(0.05)
                except Exception as e:
                    # Don't raise from a thread; report and exit gracefully
                    self._emit(f"[SSH Read Error] {e}\n")
                    break
        finally:
            self.is_connected = False

    # ----- Resize handling (POSIX CLI only) --------

    def _handle_resize(self, *_args) -> None:
        """Best-effort remote PTY resize based on local TTY size (POSIX only).

        Non-fatal: if stdout is not a TTY or ioctl fails, we just skip.
        """
        if IS_WINDOWS or not self.channel or not sys.stdout.isatty():
            return
        try:
            h, w, _, _ = struct.unpack(
                "HHHH",
                fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0)),
            )
            # Paramiko expects width, height (cols, rows)
            self.channel.resize_pty(width=w, height=h)
        except Exception:
            # Avoid throwing from a signal handler; keep running
            pass
