# cli_adapter2.py
# Description:  Implementation of my version of the CLI adapter.  This sits between the 
#               cli_main.py and the xxx_connection.py.  There is no connection_controller in
#               this implementation.  This is nothing fancy but builds on the work done with 
#               the 250731-BUILD version that worked the way I wanted it to work.  I am sure 
#               this breaks all kinds of architectural design approaches, but it works for CLI.
# Revision:     08/11/25: Original.  moves specific cli-user input code from cli_main.py to here.
#               08/15/25: Add Callback for Connection Classes

import sys
import time
from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, Slot, Property
from transports.connection_factory import get_connection
from utils import to_bool


class GUIAdapter(QObject):                  # added QObject for the Qt stuff
    message_ready     = Signal(str)    
    connectedChanged  = Signal(bool)   # True after TCP connects to AGWPE
    status            = Signal(str)    # human-readable status lines to show in console
    errorOccurred     = Signal(str)
    """"
    Signal is a sender to MAIN: It defines a custom event that can be emitted by an object.
    This defines a signal named message_ready.  The str type argument means the signal will always emit a Python string.
    You don't call message_ready directly - you emit it
    Example: self.send_to_gui("some text")

    Its partner call in main is:
        @Slot(str)
        def append_to_session(self, text):
           :        
    """
    def __init__(self, parent=None, local_echo=False):
        super().__init__(parent)     # ensure QObject init runs
        self.parent = parent
        self.local_echo = local_echo
        self.running = False
        self.iftype = None
        self.conn = None
        self._connected   = False
        self._bbs_linked  = False

    def send_to_gui(self, message):
        """ Takes local messages for the user and directs them to send to the display """
        self.message_ready.emit(message)

    @Slot(object)
    def _send_to_adapter(self, data):
        """
        Slot is a receiver from the xxx_connection: It marks a method as a receiver for a signal. 
        if your adapter is running in (or later moved to) a worker thread, don't touch GUI widgets 
        like lineEditSession/textEditSession directly. In Qt, widgets are not thread-safe. 
        Use a signal -> slot (or another queued call) so the update runs on the GUI thread.
        """
        # data may be bytes or str depending on your read loop
        text = data.decode(errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
        self.send_to_gui(text)   # <-- emit a plain str, no QTextCursor, no widget calls

    def set_if_type(self, iftype):
        self.iftype = iftype

    def send_to_connector(self, data):
        if not self.conn or  not self.conn.is_connected:    # IF we are not connected, then bail
            return

        if self.iftype == "serial":
            # Accept either str or bytes
            if isinstance(data, (bytes, bytearray, memoryview)):
                # Assume bytes... just send it (likely from KISS OFF sequences)
                self.conn.ser.write(data)
            else:
                # assume str; convert it to bytes
                self.conn.ser.write(str(data).encode())

        elif self.iftype in ["telnet","tcp","ssh"]:
            self.conn.send(data)                            # <-- pass str; NO .encode()
        elif self.iftype == "agwpe":
            self.conn.send_text((data).encode())            # agwpe DOES NOT require a CR '\r' for data sent to it as an EOF
        elif self.iftype == "agwpe-unproto":
            self.conn.send_text_unproto((data).encode())    # agwpe DOES NOT require a CR '\r' for data sent to it as an EOF


    def run_serial(self, mrc, cfg):
        self.iftype = "serial"
        try:
            self.conn = get_connection("serial", **cfg) 
            self.conn.register_adapter_callback(self._send_to_adapter)     # xxx_connection-to-Adaptor
            self.conn.connect()                    # connect to AGWPE.

            self._set_connected(bool(getattr(self.conn, "is_connected", False)))
            if not self._connected:
                self.send_to_gui(">>> Connection FAILED\r")
                return
            port = cfg["port"]
            baudrate = cfg.get("baudrate")            
            self.send_to_gui(f">>> Serial Connect on {port} at {baudrate} baud\r")
            mrc.add_mrc_entry("serial", cfg)      # add to the MRC list here

        except Exception as e:
            self.errorOccurred.emit(str(e))
            self.send_to_gui(f">>> ERROR: {e}\n")
            try:
                if self.conn:
                    self.conn.disconnect()
            finally:
                self._set_connected(False)


    def run_telnet(self,mrc,cfg):
        self.iftype = "tcp"
        try:
            self.conn = get_connection("tcp", **cfg)
            self.conn.register_adapter_callback(self._send_to_adapter)     # xxx_connection-to-Adaptor
            self.conn.connect()                    # connect to AGWPE.

            self._set_connected(bool(getattr(self.conn, "is_connected", False)))
            if not self._connected:
                self.send_to_gui(">>> Connection FAILED\r")
                return
            self.send_to_gui(">>> Telnet Connect SUCCESSFUL\r")
            mrc.add_mrc_entry("tcp", cfg)      # add to the MRC list here

        except Exception as e:
            self.errorOccurred.emit(str(e))
            self.send_to_gui(f">>> ERROR: {e}\n")
            try:
                if self.conn:
                    self.conn.disconnect()
            finally:
                self._set_connected(False)


    def run_agwpe_connect(self,mrc,cfg):
        self._set_connected(False)
        self.iftype = "agwpe"
 
        host = cfg["host"]
        port = cfg.get("port")            
        fmcall = cfg["fmcall"]
        self.send_to_gui(f">>> AGWPE Connecting to {host}:{port}...\n")
        try:
            self.conn = get_connection("agwpe",  **cfg)
            self.conn.register_adapter_callback(self._send_to_adapter)     # xxx_connection-to-Adaptor
            self.conn.connect()                    # connect to AGWPE.
            time.sleep(0.5)     # added 250923

            self._set_connected(bool(getattr(self.conn, "is_connected", False)))
            if not self._connected:
                self.send_to_gui(">>> Connection FAILED\r")
                return

            # Once we connect, register the operator
            self.send_to_gui(">>> AGWPE Connect SUCCESSFUL\r")

            self.conn.set_call_from(fmcall)
            self.conn.register()
            time.sleep(0.5)     # gives time for AGWPE to properly set

            if not self.conn.is_registered:
                self.send_to_gui(">>> Registration FAILED\r")
                self.conn.disconnect()
                self._set_connected(False)
                return
            self.send_to_gui(">>> Registration SUCCESSFUL\r")

        except Exception as e:
            self.errorOccurred.emit(str(e))
            self.send_to_gui(f">>> ERROR: {e}\n")
            try:
                if self.conn:
                    self.conn.disconnect()
            finally:
                self._set_connected(False)


    def run_agwpe_bbs(self,mrc,cfg):
        self.iftype = "agwpe"

        if not self.is_connected:
            return

        tocall = cfg["tocall"]
        connect = cfg["bbsconnect"]
        via = cfg["bbsvia"]
        try:
            mrc.add_mrc_entry("agwpe-bbs", cfg)      # add to the MRC list here
            self.send_to_gui(">>> Connecting to " + tocall + "\r")
            self.conn.set_call_to(tocall)
            
            if connect == 'Direct':
                self.conn.bbs_connect()
            else:
                self.conn.bbs_connect_via()
            time.sleep(0.5)

        except Exception as e:
            self.errorOccurred.emit(str(e))
            self.send_to_gui(f">>> ERROR: {e}\n")
            try:
                if self.conn:
                    self.conn.disconnect()
            finally:
                self._set_connected(False)


    def run_agwpe_unproto(self,mrc,cfg):
        self.iftype = "agwpe-unproto"

        if not self.is_connected:
            return

        tocall = cfg["unprotoid"]
        connect = cfg["unprotoconnect"]
        via = cfg["unprotovia"]

        try:
            if self.conn.is_connected:
                mrc.add_mrc_entry("agwpe-unproto", cfg)      # add to the MRC list here
                self.conn.set_call_to(tocall)
                self.send_to_gui(">>> Unproto as " + tocall + "\r")

                if connect == 'Direct':
                    self.conn.set_via('')
                else:
                    self.conn.set_via(unprotovia)
                time.sleep(0.5)

                self.conn.monitor()
                self.send_to_gui(">>> Monitor On\r")


        except Exception as e:
            self.errorOccurred.emit(str(e))
            self.send_to_gui(f">>> ERROR: {e}\n")
            try:
                if self.conn:
                    self.conn.disconnect()
            finally:
                self._set_connected(False)


    def run_ssh(self, mrc, cfg):
        self.iftype = "ssh"

        host = cfg["host"]
        port = cfg["port"]
        username = cfg["username"]
        password = cfg["password"]

        try:
            self.conn = get_connection("ssh",  **cfg)
            self.conn.register_adapter_callback(self._send_to_adapter)     # xxx_connection-to-Adaptor
            self.conn.connect()                    # connect to telnet by SSH.

            self._set_connected(bool(getattr(self.conn, "is_connected", False)))
            if not self._connected:
                self.send_to_gui(">>> Connection FAILED\r")
                return
            self.send_to_gui(">>> SSH Connect SUCCESSFUL\r")

        except Exception as e:
            self.errorOccurred.emit(str(e))
            self.send_to_gui(f">>> ERROR: {e}\n")
            try:
                if self.conn:
                    self.conn.disconnect()
            finally:
                self._set_connected(False)


    def run_test(self):
        self.iftype = "serial"
        print(f">>> Adaptor > run_test > pressed")
        self.send_to_gui(f">>> Adaptor > run_test > pressed\n")

    def get_connect_status(self) -> bool:
        return self.conn.is_connected 


    # ---- properties (optional, handy for polling) ----
    @Property(bool, notify=connectedChanged)
    def is_connected(self): return self._connected


    # ---- internal setters that emit signals only on change ----
    def _set_connected(self, v: bool):
        if v != self._connected:
            self._connected = v
            self.connectedChanged.emit(v)



        

