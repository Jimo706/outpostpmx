"""
Send/Receive transport adapter.

This module provides SendReceiveAdapter, a small helper that wraps a transport
connection (serial / telnet / ssh / etc.) and adds:

- A thread-safe inbound text buffer (append-only until drained)
- Convenience methods to send a command line
- Expect-style regex waiting (expect / expect_any) with timeouts
- A "wait_quiet" helper to avoid prompt tail from being misattributed to the
  next command
- OPTIONAL: a transcript callback that captures raw RX/TX (Outpost Classic style)

Architectural role
------------------
- The underlying BaseConnection owns I/O and calls the adapter callback whenever
  new text arrives.
- The SendReceiveSession / protocol adapters use this class as their primary
  interface for "send a command and wait for a prompt".

Important behavior notes
------------------------
- This adapter is intentionally *text-based*. Any bytes are expected to have been
  decoded to str by the underlying connection layer.
- Patterns are treated as regular expressions and searched anywhere in the buffer.
- Cancellation is handled at higher layers; expect() only times out.
"""

from __future__ import annotations

import threading
import time
import re
from typing import Callable, Iterable, Optional

from transports.connection_base import BaseConnection


TranscriptFn = Callable[[str], None]


class SendReceiveAdapter:
    """
    Thread-safe buffering + expect-style helpers for a BaseConnection.

    The BaseConnection is expected to call register_adapter_callback(cb) where cb
    is invoked with decoded text data (str). This adapter accumulates all inbound
    data into an internal buffer protected by a lock.

    Optional transcript support:
      - If transcript is provided, the adapter will emit raw TX and RX strings:
          ">> <line>\\n" for send_line()
          "<< <data>"    for inbound chunks as received (may include newlines)

    Typical usage in SendReceiveSession:

        adapter.send_line("C W1XSC-1")
        adapter.expect(r"Connected", timeout=30.0)
        adapter.wait_quiet()
        banner = adapter.drain_buffer()

    This class is deliberately small and does not interpret protocol state. That
    work belongs in BBSProtocolAdapter and SendReceiveSession.
    """

    def __init__(self, conn: BaseConnection, *, transcript: Optional[TranscriptFn] = None, show_tx=True):
        """
        Create an adapter around an open connection.

        Args:
            conn: A connection that supports register_adapter_callback(cb) and
                either send(str) or write(bytes).
            transcript: Optional callable that receives raw transcript text.
                Use this to build a "Conversation" log (TX/RX) in the UI.
        """
        self._conn = conn
        self._buffer = ""
        self._lock = threading.Lock()
       
        self._transcript: Optional[TranscriptFn] = transcript
        self._show_tx = show_tx

        # The connection calls _on_rx() whenever new decoded text arrives.
        self._conn.register_adapter_callback(self._on_rx)

    # ------------------------------------------------------------------
    # Transcript helper
    # ------------------------------------------------------------------
    def _t(self, text: str) -> None:
        """Emit transcript text if enabled (best-effort; never raises)."""
        fn = self._transcript
        if not fn:
            return
        try:
            fn(text)
        except Exception:
            # Transcript must never break the session.
            pass

    # ------------------------------------------------------------------
    # RX handling
    # ------------------------------------------------------------------
    def _on_rx(self, data: str) -> None:
        """
        Connection callback: append inbound data to the internal buffer.

        This method may be invoked from a background reader thread, so all buffer
        mutation must be protected by the lock.
        """
        if data:
            # Raw RX chunk (may contain newlines, partial lines, etc.)
            #self._t(f"<< {data}")      # 260114, replaced with next for no direction pointers
            self._t(f"{data}")
        with self._lock:
            self._buffer += data

    # ------------------------------------------------------------------
    # TX helpers
    # ------------------------------------------------------------------
    def send_line(self, line: str) -> None:
        """
        Send a line/command to the connection.

        Behavior:
        - Logs TX to transcript as: ">> <line>\\n"
        - If the connection exposes send(str), we pass the string as-is.
        - If the connection exposes write(bytes), we append CR and encode to UTF-8.

        Note:
        - For packet/TNC command flows, CR ("\\r") is typically the correct line ending.
        - For telnet command flows, it is CRLF ("\\r\\n") is typically the correct line ending.
        """
        line = "" if line is None else str(line)

        # Transcript (Outpost Classic style)
        # show_tx=True for telnet.  
        # show_tx=False for serial since the TNC echo's everything back
        ### CONFIRMED:  print(f">>>>> _show_tx={self._show_tx}")
        if self._show_tx:
            self._t(f"{line}\n")

        if hasattr(self._conn, "send"):
            # Preferred API: let the transport decide about CR/LF
            self._conn.send(line)
        elif hasattr(self._conn, "write"):
            # Direct bytes path: append CR (TNC style)
            payload = (line + "\r").encode("utf-8", errors="replace")
            self._conn.write(payload)
        else:
            raise AttributeError(f"{type(self._conn).__name__} has neither send() nor write()")

    # ------------------------------------------------------------------
    # Expect helpers
    # ------------------------------------------------------------------
    def expect(self, pattern: str, timeout: float = 10.0) -> None:
        """
        Wait until a regex pattern is observed in the inbound buffer.

        Args:
            pattern: Regular expression searched against the entire buffer.
            timeout: Maximum seconds to wait.

        Raises:
            TimeoutError: if the pattern is not seen within timeout.
        """
        self.expect_any([pattern], timeout)

    def expect_any(self, patterns: Iterable[str], timeout: float = 10.0) -> None:
        """
        Wait until *any* of the given regex patterns are observed in the buffer.

        This is useful when multiple prompts or success/failure strings are acceptable.

        Args:
            patterns: Iterable of regular expression strings.
            timeout: Maximum seconds to wait.

        Raises:
            TimeoutError: if none of the patterns are seen within timeout.
        """
        # Convert to list once so we can safely re-use it in the error message.
        pats = list(patterns)
        end = time.time() + timeout
        compiled = [re.compile(p) for p in pats]
        ### print(f">>>>> compiled={compiled}")

        while time.time() < end:
            with self._lock:
                buf = self._buffer

            for rx in compiled:
                if rx.search(buf):
                    return

            # Polling loop; small sleep keeps CPU reasonable.
            time.sleep(0.05)

        raise TimeoutError(f"Timeout waiting for any of: {pats}")


    # NOTE (Buffer Discipline):
    # Keep buffer scans lock-consistent with expect_any(). On high-latency links the
    # reader thread can append while we are scanning; protect _buffer reads with _lock.
    # (If this is ever changed, update both expect_any() and expect_any_match() together.)
    # 260104, handle BBS prompt OR TNC '***<error>' string
    # 260118, Make expect_any_match() lock-consistent
    def expect_any_match(self, patterns: Iterable[str], timeout: float = 10.0) -> str:
        """
        Like expect_any(), but returns the *pattern string* that matched.

        Patterns are generally regex strings. For robustness, if a pattern fails
        to compile as regex, it is treated as a literal string (via re.escape()).
        This prevents crashes when callers accidentally provide literal prompts
        that contain regex metacharacters (e.g., ') >').
        """
        pats = list(patterns)  # freeze iterable for consistent timeout message
        ### CONFIRMED.  print(f">>>>> pats={pats} <<<<<")
        end = time.time() + timeout

        compiled = []
        for p in pats:
            try:
                rx = re.compile(p)
            except re.error:
                # Fall back to literal match if pattern isn't valid regex
                rx = re.compile(re.escape(p))
            compiled.append((p, rx))

        while time.time() < end:
            with self._lock:
                buf = self._buffer

            for p, rx in compiled:
                if rx.search(buf):
                    return p

            time.sleep(0.05)

        raise TimeoutError(f"Timeout waiting for any of: {pats}")



    # ------------------------------------------------------------------
    # Buffer management
    # ------------------------------------------------------------------
    def drain_buffer(self) -> str:
        """
        Return and clear the accumulated inbound buffer.

        Use this to capture the response text once an expect() condition has been met.
        """
        with self._lock:
            data = self._buffer
            self._buffer = ""
        return data

    def wait_quiet(self, quiet_seconds: float = 0.20, timeout: float = 2.0) -> None:
        """
        Wait until the inbound buffer stops changing for quiet_seconds.

        Why this exists:
        Some interfaces deliver output in bursts; a prompt can arrive slightly late.
        If we immediately send the next command, that late prompt tail can be mistaken
        as the response to the *next* command. Waiting for a short quiet period helps
        separate responses.

        Args:
            quiet_seconds: Required duration with no buffer growth to be considered "quiet".
            timeout: Maximum seconds to wait for quiet.

        Raises:
            TimeoutError: if the buffer never becomes quiet before timeout.
        """
        end = time.time() + timeout

        with self._lock:
            last_len = len(self._buffer)
        last_change = time.time()

        while time.time() < end:
            with self._lock:
                cur_len = len(self._buffer)

            if cur_len != last_len:
                last_len = cur_len
                last_change = time.time()
            elif (time.time() - last_change) >= quiet_seconds:
                return

            time.sleep(0.02)

        raise TimeoutError("Timeout waiting for quiet buffer")
