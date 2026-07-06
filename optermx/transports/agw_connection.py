"""
agwpe_connection.py - AGWPE client for optermx (blocking socket + reader thread).

Responsibilities:
- Connect to the AGWPE TCP service and maintain a background reader thread
- Build/parse AGWPE 36-byte headers and deliver payloads to the GUI adapter
- Provide small command helpers (register, connect, unproto, monitor, etc.)

Length field compatibility:
- This implementation writes length to BOTH:
  * [28:30] as a 16-bit little-endian short (for older code)
  * [32:36] as a 32-bit little-endian (common in AGWPE examples)
- On receive, it prefers the 32-bit value at [32:36]; if zero, it falls back to [28:30].
"""

from __future__ import annotations

import select
import socket
import struct
import threading
from typing import Callable, Optional

from utils import bin2ascii
from .connection_base import BaseConnection
from .exceptions import (
    AGWConnectionError,
    AGWReadError,         # (kept for parity; we emit to UI rather than raising from threads)
    AGWProtocolError,     # (kept for future use)
)

AGW_HDR_LEN = 36


class AGWConnection(BaseConnection):
    """AGWPE TCP transport with background reader thread.

    Args:
        host: AGWPE server, typically '127.0.0.1'.
        port: AGWPE port, typically 8000.

    Adapter callback:
        Call register_adapter_callback(cb) where cb(str) receives text/status lines.

    Threading:
        - connect() starts a daemon reader thread.
        - disconnect() signals stop, closes the socket, and joins the thread.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000
        ) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

        # Inputs to header builder
        self.port_out = 0
        self.port_inb = 0
        self.call_from = b''
        self.call_to = b''
        self.via = []
        self.logon = b''
        self.password = b''
        self.tx_message: bytes = b''

        # Receive state
        self.rx_buffer = bytearray()
        self.rx_data_kind: str = ""
        self.msg_len = 0
        self.version = ""
        self.ports = ""
        self.is_registered = False
        self.is_bbs_connected = False
        self.rx_message: bytes = b""
        self.rx_data_ok = False

        # Runtime
        self.agw_read_thread: Optional[threading.Thread] = None
        self.running = False
        self.debug_logging = False
        self.is_connected = False
        self._send_to_adapter: Optional[Callable[[str], None]] = None
        self._suppress_emit = False         # special case for is_registered and printing

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
        """Connect to AGWPE and start the reader thread.

        Returns:
            True on success; False if the connection failed (an error line is emitted).
        """
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=5.0)
            self.sock.setblocking(True)  # recv guarded by select()
            self.is_connected = True

            if not (self.agw_read_thread and self.agw_read_thread.is_alive()):
                self.running = True
                self.agw_read_thread = threading.Thread(
                    target=self._read_loop, daemon=True, name="AgwpeReadLoop"
                )
                self.agw_read_thread.start()

            self._emit(f"[Connected] AGWPE {self.host}:{self.port}\n")
            return True

        except Exception as e:
            self.sock = None
            self.is_connected = False
            self._emit(f"[AGWPE Connect Error] {e}. The AGWPE application may not be running.\n")
            return False

    def disconnect(self) -> None:
        """
        Cleanly tear down the AGWPE connection. Stop the reader thread and close the socket.
        Safe to call multiple times.
        """
        # 1) Flip flags so the reader loop exits ASAP
        self.running = False

        # 2) Politely tell the BBS to disconnect before killing the socket
        if self.sock and getattr(self, "is_bbs_connected", False):
            try:
                self.bbs_disconnect()                     # send AGWPE 'disconnect' frame
                self._emit(">>> BBS Disconnected\n")
            except Exception as e:
                self._emit(f"[AGWPE bbs_disconnect error] {e}\n")
            finally:
                self.is_bbs_connected = False

        # 3) Unblock any blocking recv in the reader thread
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass

        # 4) Join the reader thread (but never from itself)
        if self.agw_read_thread and self.agw_read_thread.is_alive() and threading.current_thread() is not self.agw_read_thread:
            try:
                self.agw_read_thread.join(timeout=1.0)
            except Exception:
                pass

        # 5) Close the socket last
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

        # 6) Clear state and notify
        self.sock = None
        self.agw_read_thread = None
        self.is_connected = False
        try:
            # If you have a Qt signal, emit it here; otherwise ignore
            self.connected_changed.emit(False)  # optional
        except Exception:
            pass
        self._emit("[Disconnected] AGWPE\n")

        """
        self.running = False
        try:
            if self.is_bbs_connected:
                self.bbs_disconnect()
                self._emit(">>> BBS Disconnected\n")
                self.sock = None
                self.is_connected = False
        except Exception:
            pass

        if self.sock:
            try:
                # Unblock any waiting recv
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

        if self.agw_read_thread and self.agw_read_thread.is_alive():
            self.agw_read_thread.join(timeout=1.0)

        self.is_connected = False
        self._emit("[Disconnected] AGWPE\n")
        """

    # ---------------- Public API --------------------

    def send(self) -> str:
        """Compatibility placeholder (unused; GUI calls higher-level helpers)."""
        return ""

    def receive(self) -> str:
        """Return the last received message as text (primarily for testing)."""
        return self.rx_message.decode("utf-8", errors="ignore") 

    # Small command helpers (write the correct DataKind)
    def logon_cmd(self) -> None:
        self.send_frame("P")

    def register(self) -> None:
        self.send_frame("X")

    def bbs_connect(self) -> None:
        self.send_frame("C")

    def bbs_connect_via(self) -> None:
        self.tx_message = self.via
        self.send_frame("v", self.tx_message)   

    def bbs_disconnect(self) -> None:
        self.send_frame("D")

    def unregister(self) -> None:
        self.send_frame("x")

    def request_version(self) -> None:
        self.send_frame("R")

    def request_ports(self) -> None:
        self.send_frame("G")

    def unproto(self) -> None:
        self.send_frame("M")  # verify your DataKind mapping vs spec

    def unproto_via(self) -> None:
        self.send_frame("V")

    def monitor(self) -> None:
        self.send_frame("m")

    def send_text(self, text: str) -> None:
        """Send connected-mode text (uses 'D' DataKind)."""
        # self.tx_message = text.encode("utf-8", "replace")
        self.tx_message = text                          # ORIGINAL
        self.send_frame("D", self.tx_message)

    def send_text_unproto(self, text: str) -> None:
        """Send connected-mode text (uses 'K' DataKind)."""
        # self.tx_message = text.encode("utf-8", "replace")
        self.tx_message = text                          # ORIGINAL
        self.send_frame("M", self.tx_message)

    # ---------------- Frame I/O ---------------------

    def send_frame(self, kind: str, message: bytes = b"") -> None:
        """TRANSMIT Path: Build and transmit a single AGWPE frame."""
        if isinstance(message, str):
            message = message.encode("utf-8", "replace")

        header = self._build_header(kind, message)

        if isinstance(header, str):
            header = header.encode("ascii", "replace")
        frame = header + message                        # append the message after the header

        if self.debug_logging:
            self._emit(f">>> SEND len = {len(message)}\r")
            self._emit(bin2ascii(header + message))

        if  self.sock is None:
            raise AGWConnectionError("Cannot send: socket is not connected.")
        try:
            self.sock.sendall(frame)
        except Exception as e:
            raise AGWConnectionError(f"Failed to send frame: {e}") from e


    def _build_header(self, kind: str, message: bytes) -> bytes:
        """TRANSMIT Path: Construct a 36-byte AGWPE header for the outgoing frame.

        Fields (byte offsets):
          [0]      : Port (0 for default)
          [4]      : DataKind (ASCII)
          [6]      : PID (0xF0 for UI text)
          [8:18]   : CALL_FROM (10 bytes, NUL-padded)
          [18:28]  : CALL_TO   (10 bytes, NUL-padded)
          [28:30]  : length (uint16 little-endian)  <-- written for compatibility
          [32:36]  : length (uint32 little-endian)  <-- preferred by many implementations
        """
        header = bytearray(AGW_HDR_LEN)
        header[0] = 0
        header[4] = ord(kind[:1])
        header[6] = 0xF0
        header[8:18] = (self.call_from or b"").ljust(10, b"\x00")
        header[18:28] = (self.call_to or b"").ljust(10, b"\x00")

        msg_len = len(message)
        # 16-bit length (legacy)
        header[28] = msg_len & 0xFF
        header[29] = (msg_len >> 8) & 0xFF
        # 32-bit length (common)
        struct.pack_into("<I", header, 32, msg_len)

        return bytes(header)

    # ---------------- Reader thread ----------------

    def _read_loop(self) -> None:
        """Continuously read from AGWPE, assemble frames, and emit text to the adapter."""
        try:
            while self.running and self.sock:
                try:
                    # Wait briefly for readability to avoid blocking indefinitely
                    ready, _, _ = select.select([self.sock], [], [], 0.01)
                    if not ready:
                        continue

                    if self.sock:
                        data = self.sock.recv(4096)
                        #print(f"AGW>READ_LOOP>data = self.sock.recv = {data}")
                    if not data:
                        break  # remote closed
                    self._process_frame(data)

                except (OSError, ConnectionResetError) as e:
                    if self.running:
                        self._emit(f"[AGWPE Read Error] {e}\n")
                    break
        finally:
            self.is_connected = False


    def _process_frame(self, data: bytes) -> None:
        """RECEIVE Path:  Append raw bytes, extract full frames, and handle them."""
        self.rx_buffer.extend(data)

        while len(self.rx_buffer) >= AGW_HDR_LEN:
            header = self.rx_buffer[:AGW_HDR_LEN]

            # Prefer 32-bit length at [32:36]; if zero, fall back to 16-bit at [28:30].
            len32 = int.from_bytes(header[32:36], "little")
            if len32:
                msg_len = len32
            else:
                msg_len = header[28] | (header[29] << 8)

            if len(self.rx_buffer) < AGW_HDR_LEN + msg_len:
                # Incomplete frame; wait for more bytes.
                return

            frame = bytes(self.rx_buffer[:AGW_HDR_LEN + msg_len])
            del self.rx_buffer[:AGW_HDR_LEN + msg_len]

            self.rx_data_kind = chr(header[4])
            self.rx_message = frame[AGW_HDR_LEN:]
            self.rx_data_ok = True

            # Per-kind side effects / bookkeeping
            self._suppress_emit = False             # handle case where Registration result returns 0x01 success
            self._process_data_kind()

            if self._suppress_emit:
                return  # stop: control frame handled internally

            if self.debug_logging:
                self._emit(f">>> RECV: msg_len = {msg_len}\r")
                self._emit(bin2ascii(self.rx_message))

            # Emit text to UI (CR → CRLF for display friendliness)
            try:
                #print(f"AGW>RECV DEBUG>self._emit(self.rx_message.decode... {self.rx_message}")
                self._emit(self.rx_message.decode("utf-8", errors="ignore").replace("\r", "\r\n"))
            except Exception:
                # Last-resort hex dump if decoding fails unexpectedly
                self._emit(bin2ascii(self.rx_message))

    # ---------------- Kind handlers ---------------

    def _process_data_kind(self) -> None:
        """Update internal state based on DataKind and message payload."""

        k = self.rx_data_kind
        match k:
            case "P":
                # Remote Logon (no ack expected)
                pass

            case "X":
                # Registration result: 0x00 fail, 0x01 success
                if self.rx_message:
                    ok = (self.rx_message[0] == 0x01)
                    self.is_registered = ok
                    self._suppress_emit = True
                return          # <-- DO NOT forward rx_message to UI

            case "D" | "C":
                # already handled in _process_data_kind()
                pass

            case "d":
                # Disconnect result
                pass

            case "R":
                # Version: two uint16 (major, minor) at offsets [0:2], [4:6]
                if len(self.rx_message) >= 6:
                    major = self.rx_message[1] * 256 + self.rx_message[0]
                    minor = self.rx_message[5] * 256 + self.rx_message[4]
                    self.version = f"{major}.{minor}"

            case "G":
                # Ports info, up to first NUL; semicolons to newlines
                port_info = self.rx_message.split(b"\x00")[0].decode("utf-8", errors="ignore")
                self.ports = port_info.replace(";", "\n")

            case "S" | "I" | "U" | "T":
                # Monitored Supervisory / Connected Info / Unproto / "T"
                pass

            case _:
                # Unknown or unhandled kinds are ignored (could log in debug)
                if self.debug_logging:
                    self._emit(f"[AGWPE Unknown Kind '{k}'] {len(self.rx_message)} bytes\n")

    # --------------- Setters / Getters -------------

    def set_logon(self, username: str) -> None:
        """Set logon (padded to 255 bytes, NUL-terminated)."""
        self.logon = username.encode("utf-8", "replace").ljust(255, b"\x00")

    def set_password(self, password: str) -> None:
        """Set password (padded to 255 bytes, NUL-terminated)."""
        self.password = password.encode("utf-8", "replace").ljust(255, b"\x00")

    def set_call_from(self, call: str) -> None:
        """Set source callsign (10 bytes, NUL-padded)."""
        self.call_from = call.strip().upper().encode("ascii", "replace")[:10].ljust(10, b"\x00")

    def set_call_to(self, call: str) -> None:
        """Set destination callsign (10 bytes, NUL-padded)."""
        self.call_to = call.strip().upper().encode("ascii", "replace")[:10].ljust(10, b"\x00")

    def set_via(self, via_list: list[str]) -> None:
        """Set digipeater path (NUL-padded 10-byte fields for each hop)."""
        hops = [v.strip().upper().encode("ascii", "replace")[:10].ljust(10, b"\x00") for v in via_list]  #via_list is now a list, not string
        self.via = b"".join(hops)   # self.via is now bytes, not list

    def get_version(self) -> str:
        return self.version

    def get_ports(self) -> str:
        return self.ports

    def set_debug(self, debug_flag: bool) -> None:
        self.debug_logging = bool(debug_flag)

    # --------------- Utility routines -------------
    # EXCESS -- DELETE
    # def _pad10(self, s: str) -> bytes:
    #     return s.strip().upper().encode("ascii", "replace")[:10].ljust(10, b"\x00")

