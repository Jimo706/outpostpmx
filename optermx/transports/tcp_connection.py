"""
tcp_connection.py — Raw TCP transport (blocking socket + reader thread).

Responsibilities:
- Connect/disconnect to a TCP host:port
- Spawn/stop a background reader thread that forwards received text to the GUI
- Provide a simple line-oriented send() (default CR terminator for JNOS)

Notes:
- No Telnet negotiation; this is a "dumb terminal" raw socket (banners, prompts, etc.).
- Outbound encoding: UTF-8 (errors='replace'); inbound decoding likewise.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable, Optional

from .connection_base import BaseConnection
from .exceptions import TCPConnectionError, TCPReadError, TCPWriteError


class TcpConnection(BaseConnection):
    """Raw TCP transport with a background reader thread.

    Args:
        host: Remote hostname or IP address.
        port: Remote TCP port.
        connect_timeout: Seconds to wait when establishing the TCP connection.
        crlf: If True, send CRLF ('\\r\\n'); if False, send CR only ('\\r', JNOS-friendly).
        poll_sleep: Idle sleep between non-blocking recv polls (seconds).

    Threading:
        - The reader runs on a daemon thread created by connect().
        - disconnect() signals the thread to stop, closes the socket, and joins the thread.

    Adapter callback:
        - Call register_adapter_callback(cb) with a function that accepts a single str.
        - All status/incoming text is delivered via this callback.
    """

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float = 5.0,
        crlf: bool = False,
        poll_sleep: float = 0.05,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.crlf = crlf
        self.poll_sleep = poll_sleep

        self.stop_evt = threading.Event()                       # !!! ADDED 250930
        self.read_thread: Optional[threading.Thread] = None
        self.sock: Optional[socket.socket] = None
        self.running = False
        self.is_connected = False

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
        """Open the TCP socket and start the background reader thread.

        Returns:
            True on success; False if the connection could not be established.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.connect_timeout)
            s.connect((self.host, self.port))
            # Non-blocking receive loop with small sleeps to avoid busy spin
            s.settimeout(0.0)
            self.sock = s

            self.running = True
            self.stop_evt.clear()                   # !!! ADDED 250930
            self.is_connected = True
            self._emit(f">>>tcp_connect>connect: TCP to {self.host}:{self.port}\n")

            self.read_thread = threading.Thread(
                target=self._read_loop, name="TcpReadLoop", daemon=True
            )
            self.read_thread.start()
            return True

        except Exception as e:
            self.is_connected = False
            self._emit(f"[TCP Connect Error] {e}\n")
            return False

    def disconnect(self) -> None:
        """Stop the reader thread and close the socket."""
        # 1) signal stop
        self.stop_evt.set()

        # 2) wake any blocking recv
        if self.sock:
            try:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    # Already closed / not connected; ignore
                    pass
                self.sock.close()
            except Exception as e:
                self._emit(f"[TCP Close Error] {e}\n")
            finally:
                self.sock = None

       # 3) join reader thread
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.5)
            self.read_thread = None
            if self.read_thread and self.read_thread.is_alive():
                self._emit("[TCP] Reader thread did not stop within 0.5s\n")
        self.read_thread = None

        # 4) final state + notify
        self.is_connected = False
        self._emit("[Disconnected] TCP\n")


    # ---------------- I/O ---------------------------

    def send(self, command: str) -> None:
        """Encode and transmit a single command line.

        Uses CR ('\\r') by default (preferred by JNOS). Set crlf=True to send CRLF.

        Raises:
            TCPWriteError: if the socket is not open or the write fails.
        """
        if not self.sock:
            raise TCPWriteError("Socket is not open")

        try:
            line_end = "\r\n" if self.crlf else "\r"
            data = (command + line_end).encode("utf-8", errors="replace")
            self.sock.sendall(data)
        except Exception as e:
            self._emit(f"[TCP Write Error] {e}\n")
            raise TCPWriteError(str(e)) from e

    def receive(self) -> str:
        """Satisfy BaseConnection interface; unused because reading is async via thread."""
        return ""

    # ---------------- Internals ---------------------

    def _read_loop(self) -> None:
        """Continuously read from the socket and forward decoded text to the adapter."""
        try:
            while self.running and self.sock:
                try:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        # Remote closed the connection
                        break
                    self._emit(chunk.decode("utf-8", errors="replace"))
                except BlockingIOError:
                    # No data available right now; back off briefly
                    time.sleep(self.poll_sleep)
                except Exception as e:
                    self._emit(f"[TCP Read Error] {e}\n")
                    break
        finally:
            self.is_connected = False
