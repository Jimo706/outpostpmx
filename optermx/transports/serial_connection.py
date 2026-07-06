"""
serial_connection.py — Serial transport for OpTermx.

Responsibilities:
- Open/close a serial port with configured parameters
- Spawn/stop a background reader thread
- Deliver inbound text to the GUI adapter via a registered callback
- Provide a text-based send() API

Notes:
- This transport is line-agnostic: it forwards raw bytes decoded as text.
- Flow control, parity, and word length are mapped from user-friendly values.

Revision:
250913: updated docnotes, checked all error handling
"""
# 250912: need to evaluate this line
from __future__ import annotations

import sys
import threading
import time
import platform
from typing import Callable, Optional

import serial

from .connection_base import BaseConnection
from .exceptions import SerialConnectionError, SerialReadError, SerialWriteError

# check if this is a MS platform.  This will tell us what else we import.
IS_WINDOWS = platform.system() == 'Windows'
if not IS_WINDOWS:              # , TEST: changed to 'not' 
    import termios
    import tty
else:
    import msvcrt               # check; needed?

def _map_parity(parity: str) -> str:
    """Map human text to pyserial parity constants."""
    p = parity.strip().upper()
    return {
        "NONE": serial.PARITY_NONE,
        "EVEN": serial.PARITY_EVEN,
        "ODD": serial.PARITY_ODD,
        "MARK": serial.PARITY_MARK,
        "SPACE": serial.PARITY_SPACE,
    }.get(p, serial.PARITY_NONE)

def _map_databits(bits: int) -> int:
    """Map human bits to pyserial bytesize constants."""
    return {
        5: serial.FIVEBITS,
        6: serial.SIXBITS,
        7: serial.SEVENBITS,
        8: serial.EIGHTBITS,
    }.get(bits, serial.EIGHTBITS)

def _map_stopbits(stops: int | float) -> float:
    """Map human stop bits to pyserial stopbits constants."""
    return {
        1: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO,
    }.get(stops, serial.STOPBITS_ONE)

def _map_flowcontrol(flow: str) -> tuple[bool, bool]:
    """Map flow control string to (rtscts, dsrdtr)."""
    f = flow.strip().upper()
    if f in {"RTS/CTS", "RTSCTS"}:
        return True, False
    if f in {"DSR/DTR", "DSRDTR"}:
        return False, True
    return False, False


class SerialConnection(BaseConnection):         # inherits from the base class
    """Blocking Serial transport with background reader thread.

    Args:
        port: OS serial port name (e.g., 'COM3', '/dev/ttyUSB0').
        baudrate: Port speed.
        databits: 5, 6, 7, or 8.
        stopbits: 1, 1.5, or 2.
        parity: One of 'None', 'Even', 'Odd', 'Mark', 'Space' (case-insensitive).
        flowcontrol: 'RTS/CTS', 'DSR/DTR', or 'None'.

    Callback:
        The GUI/adapter must call register_adapter_callback(cb) with a function
        that accepts a single `str` argument to receive inbound text and status lines.

    Threading:
        A daemon thread reads the port; `disconnect()` will stop and join the thread.

    Raises:
        SerialConnectionError: on open failure.
    """
    
    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        databits: int = 8,
        stopbits: int | float = 1,
        parity: str = "None",
        flowcontrol: str = "RTS/CTS",
        ) -> None:
        
        self.port = port
        self.baudrate = baudrate
        self.databits = databits
        self.stopbits = stopbits
        self.parity = parity
        self.flowcontrol = flowcontrol
        
        self.ser: Optional[serial.Serial] = None
        self.read_thread: Optional[threading.Thread] = None
        self.running = False
        self.old_settings = None        # POSIX terminal restore
        #self._send_to_adapter = None    # Initialize variable that holds the 'cb' Destination function
        self._send_to_adapter: Optional[Callable[[str], None]] = None
        self.is_connected = False

    # ------- Adapter wiring -------------------------------------------------

    def register_adapter_callback(self, cb: Callable[[str], None]) -> None:
        """Register the adapter callback to receive text from this transport."""
        self._send_to_adapter = cb

    def _emit(self, text: str) -> None:
        """Safely emit text to adapter if available."""
        if self._send_to_adapter:
            self._send_to_adapter(text)

    # ------- Lifecycle ------------------------------------------------------

    def connect(self):
        """Open the serial port and start the reader thread.
        Debug:100        
        Returns:
            True if the port was opened; False if open failed (error already reported).

        Side effects:
            - Sets `is_connected`
            - On POSIX, sets terminal stdin to raw mode (so keystrokes pass through)
        """
        try:
            bytesize = _map_databits(self.databits)
            stop = _map_stopbits(self.stopbits)
            parity = _map_parity(self.parity)
            rtscts, dsrdtr = _map_flowcontrol(self.flowcontrol)

            #self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=0.1,
                bytesize=bytesize,
                stopbits=stop,
                parity=parity,
                rtscts=rtscts,
                dsrdtr=dsrdtr,
            )

            self.running = True
            self.is_connected = True
            # self._send_to_adapter(f">>>serial_connect>connect: Serial on {self.port} @ {self.baudrate} baud\n") # handled by adapter

            """ COMMENTED OUT.
            remove/disable the tty.setraw() calls in serial_connection.py and ssh_connection.py. 
            We do not need terminal stdin raw mode in a PyQt GUI app because keyboard input is handled by Qt widgets.

            if not IS_WINDOWS:
                # On Unix / POSIX only: save and set stdin to raw mode (for TTY passthrough use-cases).
                fd = sys.stdin.fileno()
                self.old_settings = termios.tcgetattr(fd)
                tty.setraw(fd)
            """

            # start the _read_loop thread
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True, name="SerialReadLoop")
            self.read_thread.start()
            return True

        except serial.SerialException as e:
            self.is_connected = False
            self._emit(f"[Serial Open Error(101)] {e}\n")
            return False              # tell the calling program it failed

    def disconnect(self):
        """Stop the reader thread, restore lines/terminal, and close the serial port.
           Debug:200        
        
        """
        # --- reentrancy guard ---
        if getattr(self, "_disconnecting", False):
            return False
        self._disconnecting = True

        was_connected = getattr(self, "is_connected", False)
        try:
            # 1) tell the reader loop to stop
            self.running = False

            # 2) try to unblock any blocking read
            #    (cancel_read is available on some platforms/pyserial builds)
            try:
                if self.ser and hasattr(self.ser, "cancel_read"):
                    self.ser.cancel_read()
            except Exception:
                pass

            # 3) join the reader thread.
            #     The thread knows it should stop (self.running = False).
            #     Any blocking call is unblocked (cancel_read or close).
            #     join() waits briefly to ensure the thread really ended.
            # Join reader thread to avoid zombie threads.
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=0.5)
            self.read_thread = None

            # 4) restore RTS/DTR lines before close
            try:
                self.ser.rts = False
                self.ser.dtr = False
            except Exception:
                pass

            # 5) and close the port
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception as e:
                    self._send_to_adapter(f"[Serial Close Error(201)] {e}")
                self.is_connected = False

            # 6) Restore POSIX terminal mode if we changed it.
            if not IS_WINDOWS and self.old_settings:
                fd = sys.stdin.fileno()
                try:
                    if sys.stdin.isatty():
                        termios.tcsetattr(fd, termios.TCSADRAIN, self.old_settings)
                except Exception:
                    pass    # non-fatal restore failure
            
            # 7) Reset reference last, after cleanup/logging
            if self.ser is not None and self.ser.is_open:
                self.ser.close()        # Frees the port, Releases resources, Clears buffers, Prevents errors
            self.ser = None

        finally:
            self._send_to_adapter(f"[Disconnected] {self.port}\n")


    # ------- I/O ------------------------------------------------------------
    def send(self, command: str | bytes) -> None:
        """Encode and transmit data to the serial port.

        Accepts:
        - str   -> encoded as UTF-8
        - bytes -> written exactly as supplied, for Ctrl-C/KISS/etc.

        Raises:
            SerialWriteError: if the port is not open or write fails.
        """
        if not (self.ser and self.ser.is_open):
            raise SerialWriteError("Serial port is not open(301)")

        try:
            if isinstance(command, (bytes, bytearray, memoryview)):
                data = bytes(command)
            else:
                data = str(command).encode("utf-8", errors="replace")

            self.ser.write(data)

        except Exception as e:
            self._emit(f"[Serial Write Error(302)] {e}\n")
            raise SerialWriteError(str(e)) from e



    def receive(self) -> str:
        """Satisfy BaseConnection interface (unused for async serial)."""
        return ""

    # ------- Internals ------------------------------------------------------

    def _read_loop(self) -> None:
        """Background reader: forwards any available bytes to the adapter."""
        Debug:400        
 
        try:
            while self.running and self.ser and self.ser.is_open:
                try:
                    waiting = self.ser.in_waiting
                except Exception:
                    waiting = 0

                if waiting:
                    try:
                        data = self.ser.read(waiting)
                        self._emit(data.decode("utf-8", errors="replace"))
                    except Exception as e:  # noqa: BLE001
                        # Report, then bail out gracefully.
                        self._emit(f"[Serial Read Error(401)] {e}\n")
                        raise SerialReadError(str(e)) from e
                else:
                    time.sleep(0.05)
        finally:
            # Ensure flags make sense if the loop exits unexpectedly.
            self.is_connected = False


