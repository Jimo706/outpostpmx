# services/send_receive_session.py
"""
Send/Receive session engine (non-UI).

This module implements the core orchestration logic for a *single* manual
Send/Receive session. It is UI-agnostic and intended to be run inside a
worker thread managed by SendReceiveSessionDialog.

Responsibilities:
- Snapshot active configuration (Station, Tactical, Interface, BBS, settings)
- Open and manage the underlying transport connection
- Drive the TNC/BBS login and protocol handshake
- Send queued outbound messages
- Retrieve and store inbound messages
- Perform best-effort cleanup on cancel or failure

Design notes:
- This class coordinates adapters (transport, BBS protocol, persistence).
- UI updates are not performed here; progress is reported via the injected logger.
- Cancellation is cooperative via a stop_requested() callback.
"""
from __future__ import annotations

import time
import re
import threading  # (ok even if not used elsewhere)
import hashlib    # required for the DB overwrite issue

from dataclasses import dataclass
from datetime import datetime, timezone         # required for data/time processing

from typing import Optional, Iterable

from transports import get_connection, BaseConnection
from transports.adapters.send_receive_adapter import SendReceiveAdapter

from services.system_config_service import SystemConfigService
from services.sqlite_message_service import SqliteMessageService
from services.message_print_service import MessagePrintService, PrintableMessage

from data.message_model import MessageState, Direction
from data.message_repo import MessageRepository
from services.node_path_executor import NodePathExecutor
from services.bbs_protocol_adapter import BBSProtocolAdapter

from services.bbs_protocol_adapter import parse_sid
from services.bbs_spec_loader import BBSSpecLoader
from services.path_script_runner import (
    PathScriptAbortedError,
    PathScriptContext,
    PathScriptError,
    PathScriptRunner,
)
from services.bbs_send_formatter import build_send_blocks

from pprint import pformat                      # required for pformat
from email.utils import parsedate_to_datetime   # required for data/time processing
#P132
from services.message_settings import load_message_settings, allocate_next_mid

WIRE_TAG_RDR = "!RDR!"
WIRE_TAG_URGENT = "!URG!"
WIRE_TAG_BASE64 = "!B64!"
WIRE_TAGS = (WIRE_TAG_RDR, WIRE_TAG_URGENT, WIRE_TAG_BASE64)


@dataclass(frozen=True)
class SessionSnapshot:
    """
    Immutable snapshot of configuration needed for a session run.

    Captured once at session start so a mid-session configuration change
    (e.g., selecting a different BBS) does not affect the active run.
    
    rev 260310: expanded to handle bbs_login credentials
    """
    station: object
    tactical: Optional[object]
    interface: object
    bbs: object
    bbs_logon: Optional[object]
    active_operator_id: str
    bbs_connect_call: str
    send_receive_settings: object
    message_settings: object

class SessionAbortRequested(RuntimeError):
    """Raised when the operator presses Cancel and an immediate abort is required."""
    pass

class SendReceiveSession:
    """
    Orchestrate a single manual Send/Receive session.

    Intended usage:
    - Construct once per run
    - Call run() exactly once

    High-level flow:
      snapshot → connect → login → send outbound → receive inbound → logout → cleanup
    """
    # 260102, added transcript=None, 
    def __init__(
        self,
        system_config: SystemConfigService,
        message_repo: MessageRepository,
        message_service: SqliteMessageService,
        logger=print,
        transcript=None, 
        stop_requested=None,
        messages_received=None,
    ) -> None:
        self._system_config = system_config
        self._message_repo = message_repo
        self._message_service = message_service
        self._log = logger
        self._stop_requested = stop_requested or (lambda: False)
        self._messages_received = messages_received or (lambda _payload: None)

        self._conn: Optional[BaseConnection] = None
        self._adapter: Optional[SendReceiveAdapter] = None

        # 260102, session window
        self._transcript = transcript or (lambda _s: None)        

        self._spec_loader = BBSSpecLoader()
        self.snap = None
        # Abort/disconnect support (Outpost Classic-style Cancel/Abort)
        self._abort_lock = threading.Lock()
        self._abort_done = False

        self.trace = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        """
        Called from main_window.py > send_receive_session_dialog.py
        Execute the Send/Receive session.
        
        This method blocks until completion or cooperative cancellation.
        It should be called from a worker thread (not the UI thread).
        rev: 260312: 
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession.run")


        snap = self._take_snapshot()                    # get a view of the active config for this run.
        self.snap = snap                                # added as a global variable
        self._log("Send/Receive: starting session")

        try:
            self._check_stop()                          # there is nothing to abort yet
            self._open_connection(snap)                 # Open the underlying transport connection based on the active Interface profile.
            self._check_stop_and_abort()                # chek if "cancel" was pressed, then abort 

            self._login_bbs(snap)                      # based on snapshot taken above
            self._check_stop_and_abort()

            if not self._bbs_protocol_ready(snap.bbs):
                self._log("Send/Receive: BBS protocol adapter not wired yet (have BBSProfile, missing parsers).")
                self._log("Send/Receive: stopping after connect (OK for MVP UI test).")
                return

            self._send_outbound(snap)
            self._check_stop_and_abort()

            self._receive_inbound(snap)
            self._check_stop_and_abort()

            self._logout(snap)

        except SessionAbortRequested:
            self._log("Send/Receive: session aborted by operator")

        except Exception as e:
            self._log(f"ERROR: Send/Receive failed: {e}")
            raise

        finally:
            self._close_connection()

            if self._stop_requested():  # 260226 JFIX
                self._log("Send/Receive: canceled")

            self._log("Send/Receive: session complete")


    def abort(self) -> None:
        """
        Best-effort immediate abort/disconnect (Outpost Classic behavior).

        Intended semantics:
        - TNC_TAPR (serial): send Ctrl-C, CR, then 'D'
        - TNC_SCS  (serial): send 'D'
        - TELNET/AGWPE: close/disconnect transport

        This method is idempotent and safe to call from *any* thread.
        It must never raise.
        rev: 260312: updated
             260317: move the debug log after the idempotent guard 
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession.abort")

        # Idempotent / thread-safe
        try:
            with self._abort_lock:
                if self._abort_done:
                    return
                self._abort_done = True
        except Exception:
            pass
        ### self._log("***DEBUG: Send/Receive: abort() CALLED")

        conn = getattr(self, "_conn", None)
        if not conn:
            return

        # Determine interface type from the captured snapshot (if available)
        iface_type = ""
        try:
            snap = getattr(self, "snap", None)
            iface = getattr(snap, "interface", None) if snap else None
            data = getattr(iface, "data", None) if iface else None
            if isinstance(data, dict):
                iface_type = (str(data.get("interface_type", "")) or "").strip().upper()
        except Exception:
            iface_type = ""

        try:
            # --- Serial TNCs ---
            if iface_type == "TNC_SCS":
                ### self._log(f"***DEBUG: abort()>iface_type = {iface_type}")
                try:
                    if getattr(self, "_adapter", None):
                        self._adapter.send_line("D")
                        ### self._log("***DEBUG: abort()>send_line = D")
                    elif hasattr(conn, "send"):
                        conn.send("D")
                        ### self._log("***DEBUG: abort()>conn.send = D")
                    elif hasattr(conn, "write"):
                        conn.write(b"D\r")
                        ### self._log("***DEBUG: abort()>conn.write = b'D\\r'")
                except Exception:
                    pass

            elif iface_type in ("TNC_TAPR", "", None):
                # TAPR/default serial-TNC: Ctrl-C + CR + D with tiny pauses
                try:
                    if hasattr(conn, "write"):
                        conn.write(b"\x03")       # Ctrl-C
                        ### self._log("***DEBUG: abort()>conn.write = Ctrl-C")
                        time.sleep(0.10)

                        conn.write(b"\r")         # CR
                        ### self._log("***DEBUG: abort()>conn.write = CR")
                        time.sleep(0.05)

                        conn.write(b"D\r")        # Disconnect
                        ### self._log("***DEBUG: abort()>conn.write = D")

                    elif hasattr(conn, "send"):
                        conn.send("\x03")
                        ### self._log("***DEBUG: abort()>conn.send = Ctrl-C")
                        time.sleep(0.10)

                        conn.send("\r")
                        ### self._log("***DEBUG: abort()>conn.send = CR")
                        time.sleep(0.05)

                        conn.send("D\r")
                        ### self._log("***DEBUG: abort()>conn.send = D")

                    elif getattr(self, "_adapter", None):
                        # Fallback: send_line appends CR; acceptable as last resort
                        self._adapter.send_line("\x03")
                        ### self._log("***DEBUG: abort()>send_line = Ctrl-C")
                        time.sleep(0.10)

                        self._adapter.send_line("D")
                        ### self._log("***DEBUG: abort()>send_line = D")
                except Exception:
                    pass

                # Give the TNC a brief chance to process the break/disconnect
                try:
                    time.sleep(0.20)
                except Exception:
                    pass

            # --- Other transports (best-effort) ---
            else:
                self._log(f"***DEBUG: abort()>iface_type = {iface_type}; closing transport")

        finally:
            # The critical part: force any blocking reads/expect loops to unwind.
            try:
                disc = getattr(conn, "disconnect", None)
                if callable(disc):
                    disc()
                else:
                    close = getattr(conn, "close", None)
                    if callable(close):
                        close()
            except Exception:
                pass

    def _check_stop(self) -> None:
        """Raise if the operator has requested cancel."""
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._check_stop")

        if self._stop_requested():
            raise SessionAbortRequested("Operator aborted session")

    def _check_stop_and_abort(self) -> None:
        """Abort/disconnect and raise if the operator has requested cancel."""
        # if self.trace: 
        #     self._log(f">>>>>TRACE -- SendReceiveSession._check_stop_and_abort")

        if self._stop_requested():
            self._log("Send/Receive: cancel requested; issuing abort/disconnect")
            self.abort()
            raise SessionAbortRequested("Operator aborted session")


    def _bbs_protocol_ready(self, bbs: object) -> bool:
        """
        Return True if the BBSProtocolAdapter appears to be fully wired.
        
        Used during early development to gate parsing-dependent steps.
        callable(): returns True if it's a function, method, or an object with a __call__ method, and 
                            False otherwise (e.g., if it's None, a string, or a number).
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession.bbs_protocol_ready")

        # If we don't have the parser methods, we’re still dealing with a DB profile, not a protocol adapter.
        return callable(getattr(bbs, "parse_message_listing", None)) and callable(getattr(bbs, "parse_full_message", None))


    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------
    def _take_snapshot(self) -> SessionSnapshot:
        """
        Capture a complete, stable view of the active configuration for this run.

        Includes:
        - active station / tactical / interface / BBS profile
        - operator identity used for this session's BBS logon lookup
        - resolved BBS connect call
        - matching BBS logon credentials (if any)
        - BBSProtocolAdapter preloaded with my_calls and optional login creds

        rev 260310: expanded to handle bbs_login credentials
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._take_snapshot")

        station = self._system_config.get_active_station()
        tactical = self._system_config.get_active_tactical()
        interface = self._system_config.get_active_interface()
        bbs_profile = self._system_config.get_active_bbs()
        sr = self._system_config.get_send_receive_settings()
        ms = None
        try:
            cfg = (
                getattr(self._system_config, "_config", None)
                or getattr(self._system_config, "config", None)
                or getattr(self, "_config", None)
            )

            if cfg is not None:
                ms = load_message_settings(cfg)
                self._log(
                    "Message Settings: "
                    f"request_dr={getattr(ms, 'request_dr', None)}, "
                    f"send_dr={getattr(ms, 'send_dr', None)}"
                )
            else:
                self._log("WARNING: Message Settings not loaded; no AppConfig found")
        except Exception as exc:
            self._log(f"WARNING: Message Settings load failed: {exc}")
            ms = None



        legal_call = (getattr(station, "legal_call_sign", "") or "").strip().upper()
        tactical_call = (getattr(tactical, "tactical_call_sign", "") or "").strip().upper()
        my_calls = [c for c in (legal_call, tactical_call) if c]

        active_operator_id = tactical_call or legal_call        # either tac call or legal call
        bbs_connect_call = (
            (getattr(bbs_profile, "connect_call", "") or "").strip().upper()
            or (getattr(bbs_profile, "bbs_call", "") or "").strip().upper()
        )

        bbs = BBSProtocolAdapter(bbs_profile, my_calls=my_calls) if bbs_profile else None
        bbs_logon = None

        ## self._log(f">>>>> bbs_connect_call={bbs_connect_call}, active_operator_id={active_operator_id} <<<<<")
        if bbs_connect_call and active_operator_id:
            bbs_logon = self._system_config.get_bbs_logon_for_session(
                bbs_connect_call=bbs_connect_call,
                operator_id=active_operator_id,
            )

        if bbs and bbs_logon:
            bbs.login_username = bbs_logon.login_username
            bbs.account_password = bbs_logon.account_password
            bbs.access_password = bbs_logon.access_password
            bbs.logon_name = bbs_logon.logon_name

        return SessionSnapshot(
            station=station,
            tactical=tactical,
            interface=interface,
            bbs=bbs,
            bbs_logon=bbs_logon,
            active_operator_id=active_operator_id,
            bbs_connect_call=bbs_connect_call,
            send_receive_settings=sr,
            message_settings=ms,
        )

    # ------------------------------------------------------------------
    # Connection / Login
    # ------------------------------------------------------------------
    def _open_connection(self, snap: SessionSnapshot) -> None:
        """
        Open the underlying transport connection based on the active Interface profile.
        
        Creates the BaseConnection plus a SendReceiveAdapter wrapper used for
        buffered reads and expect()/pattern matching.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._open_conection")

        p = snap.interface
        if not p:
            raise RuntimeError("Send/Receive: No active Interface selected")

        self._log(f"Connecting via interface '{getattr(p, 'friendly_name', '') or '<unnamed>'}'")

        conn_type, kwargs = self._build_conn_kwargs(p)
        ### CONFIRMED: self._log(f"DEBUG[-334]: conn_type={conn_type}, kwargs={kwargs!r}")

        # set up for displaying app-sent data
        iface_data = getattr(p, "data", {}) or {}                               # get the iface_data dict
        iface_type = (iface_data.get("interface_type") or "").strip().upper()   # look up and get the iface_type

        # show_tx = True for TELNET or AGWPE
        # show_tx = False for serial/TNC
        show_tx = iface_type in ("TELNET", "AGWPE")

        # Create transport
        self._conn = get_connection(conn_type, **kwargs)

        # Adapter wraps the connection (TX/RX buffering, expect, etc.)
        # 260102, replace this with the following:  self._adapter = SendReceiveAdapter(self._conn)
        self._adapter = SendReceiveAdapter(
            self._conn, 
            transcript=self._transcript, 
            show_tx=show_tx
        )

        # Connect (connect() now raises on failure)
        if self._stop_requested():          # 260226  JFIX
            return
        try:
            self._conn.connect()
        except Exception as e:
            self._log(f"ERROR: Interface connect failed: {e}")
            raise

        # Optional: wait for initial banner / prompt (only if the BBS object supports it)
        if snap.bbs:
            patterns = getattr(snap.bbs, "connect_success_patterns", None)
            timeout = getattr(snap.bbs, "connect_timeout", 8.0)

            if patterns:
                self._adapter.expect_any(patterns, timeout=timeout)


    def _build_conn_kwargs(self, p) -> tuple[str, dict]:
        """
        Translate an Interface profile into (connection_type, kwargs).
        
        The returned pair is suitable for transports.get_connection().
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._build_conn_kwargs")

        cfg = p.data if isinstance(getattr(p, "data", None), dict) else {}
        iface_type = (str(cfg.get("interface_type", "")) or "").strip().upper()

        ### CONFIRMED: self._log(f"***DEBUG:338-TELNET,  iface_type={iface_type}, cfg={cfg}")  # good for cfg listing

        # Serial TNCs
        if iface_type in ("TNC_TAPR", "TNC_SCS"):
            port = (str(cfg.get("tnc_com_port", "")) or "").strip()
            if not port:
                raise ValueError("InterfaceProfile.data['tnc_com_port'] is empty")

            def _int(key: str, default: int) -> int:
                v = str(cfg.get(key, "")).strip()
                return int(v) if v else default

            baud = _int("tnc_baud", 9600)
            databits = _int("tnc_data_bits", 8)
            stopbits = _int("tnc_stop_bits", 1)
            parity = (str(cfg.get("tnc_parity", "None")) or "None").strip() or "None"
            flow = (str(cfg.get("tnc_flow_control", "RTS/CTS")) or "RTS/CTS").strip() or "RTS/CTS"

            return "serial", {
                "port": port,
                "baudrate": baud,
                "databits": databits,
                "stopbits": stopbits,
                "parity": parity,
                "flowcontrol": flow,
            }

        # TELNET and AGWPE later
        if iface_type == "TELNET":
            # ------------------------------
            # Telnet Select Helper function 
            # ------------------------------
            def _first(*keys, default=""):
                for k in keys:
                    v = cfg.get(k)
                    if v not in (None, ""):
                        return str(v).strip()
                return default

            def _int_first(keys, default: int) -> int:
                for k in keys:
                    v = str(cfg.get(k, "")).strip()
                    if v:
                        return int(v)
                return default

            def _bool_first(keys, default: bool = False) -> bool:
                for k in keys:
                    v = cfg.get(k)
                    if v in (None, ""):
                        continue
                    if isinstance(v, bool):
                        return v
                    s = str(v).strip().lower()
                    if s in ("1", "true", "yes", "y", "on"):
                        return True
                    if s in ("0", "false", "no", "n", "off"):
                        return False
                return default

            host = _first("remote_host", "host", "ip_address", "address")
            if not host:
                raise ValueError("InterfaceProfile.data TELNET host is empty")

            # Optional safety: strip accidental prefixes users sometimes paste
            if host.lower().startswith("telnet://"):
                host = host[9:].strip()

            port = _int_first(("remote_port", "port"), 23)
            timeout = float(_first("remote_timeout", "connect_timeout", default="8.0") or "8.0")
            crlf = _bool_first(("telnet_crlf", "crlf"), default=False)

            # Currently, crlf = TRUE for JNOS... need better BBA switch in the future
            return "tcp", {
                "host": host,
                "port": port,
                "connect_timeout": timeout,
                "crlf": True,
            }

        if iface_type == "AGWPE":
            def _first(*keys, default=""):
                for k in keys:
                    v = cfg.get(k)
                    if v not in (None, ""):
                        return str(v).strip()
                return default

            def _timeout_seconds(value: str, default: float = 5.0) -> float:
                s = str(value or "").strip()
                if not s:
                    return default
                try:
                    n = float(s)
                except ValueError:
                    return default

                # AGWPE IRS describes this as milliseconds; be forgiving
                if n > 50:
                    return n / 1000.0
                return n

            host = _first("remote_host", "host", "ip_address", "address", default="127.0.0.1")
            port_s = _first("remote_port", "port", default="8000")
            timeout_s = _timeout_seconds(_first("remote_timeout", "connect_timeout", default="50"))

            try:
                port = int(port_s)
            except ValueError:
                raise ValueError(f"Invalid AGWPE remote_port: {port_s!r}")

            return "agwpe", {
                "host": host,
                "port": port,
                "connect_timeout": timeout_s,
            }

        raise ValueError(f"Unsupported interface_type in InterfaceProfile.data: {iface_type!r}")


    def _login_bbs(self, snap: SessionSnapshot) -> None:
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._login_bbs")

        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")

        iface = snap.interface
        iface_data = getattr(iface, "data", {}) or {}
        iface_type = (str(iface_data.get("interface_type", "")) or "").strip().upper()

        if iface_type in ("TNC_TAPR", "TNC_SCS"):
            self._login_bbs_via_tnc(snap)
            return

        if iface_type == "TELNET":
            self._login_bbs_via_telnet(snap)
            return

        if iface_type == "AGWPE":
            self._login_bbs_via_agwpe(snap)
            return

        raise RuntimeError(f"Unsupported interface_type for login: {iface_type!r}")


    def _login_bbs_via_tnc(self, snap: SessionSnapshot) -> None:
        """
        Drive the TNC and BBS login sequence.
        _login_bbs() is  the “TNC cmd prompt → connect → wait for BBS prompt” transition point.
        
        Steps:
          1) Ensure TNC command mode and prompt
          2) Issue init commands (TNC-side) if configured
          3) Connect to the BBS callsign
          4) Wait for BBS prompt and parse SID
          5) Load/bind a BBS spec (parsers, prompts, commands)
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._login_bbs_via_tnc")

        if self._stop_requested():          # 260226  JFIX
            raise SessionAbortRequested("Operator aborted session")

        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")

        iface = snap.interface
        bbs = snap.bbs

        # ------------------------------------------------------------
        # 1) Wait for TNC command prompt (from Interface profile)
        # ------------------------------------------------------------
        tnc_prompt = None
        # Prefer explicit attribute if present
        if iface is not None:
            tnc_prompt = getattr(iface, "tnc_cmd_prompt", None)

            # If your profile stores settings in iface.data (dict), check there too
            if not tnc_prompt:
                data = getattr(iface, "data", None)
                if isinstance(data, dict):
                    tnc_prompt = data.get("tnc_cmd_prompt") or data.get("command_prompt")

        tnc_prompt = (tnc_prompt or "cmd:").strip()
        if not tnc_prompt:
            raise RuntimeError("Send/Receive: TNC command prompt is not configured")

        self._log(f"Ensuring TNC command mode (prompt '{tnc_prompt}')")
        self._kick_tnc_to_cmd_mode(tnc_prompt)

        self._log(f"Waiting for TNC prompt '{tnc_prompt}'")
        self._adapter.expect(tnc_prompt, timeout=8.0)

        # ------------------------------------------------------------
        # 2) Put TNC into known state
        # 260103, need to get the TNC initialized for a connection
        # ------------------------------------------------------------
        self._prepare_tnc_known_state(snap, tnc_prompt)

        # ------------------------------------------------------------
        # 3) Send any init commands (still in TNC command mode)
        # ------------------------------------------------------------
        # 260128: check if we checked the box to always send TNC Init Commands
        send_init = bool(iface.data.get("tnc_send_init_cmds", True))

        if not send_init:
            # NO, skip the TNC init commands
            self._log("TNC init: skipped (tnc_send_init_cmds is False)")
        else:
            # YES, Send the TNC init commands
            raw_init = iface.data.get("tnc_init_before", []) or []

            # Normalize input into individual lines
            if isinstance(raw_init, str):
                init_cmds = raw_init.splitlines()
            else:
                init_cmds = list(raw_init)

            for cmd in init_cmds:
                if self._stop_requested():
                    raise SessionAbortRequested("Operator aborted session")

                # remove line endings so the transport controls CR injection
                cmd = str(cmd).rstrip("\r\n")
                if not cmd:
                    continue

                if self._stop_requested():
                    raise SessionAbortRequested("Operator aborted session")

                self._log(f"TNC init: {cmd}")
                self._send_to_tnc_and_wait_prompt(cmd, tnc_prompt, timeout=2.0)

        # ------------------------------------------------------------
        # 4) Path selection
        # ------------------------------------------------------------
        path_type = (getattr(bbs, "path_type", "") or "DIRECT").strip().upper()

        if path_type == "NODE":
            self._log("Path type NODE: running path script instead of direct BBS connect")
            self._run_path_script_if_needed(snap)

        else:
            connect_call = (getattr(bbs, "connect_call", None) or getattr(bbs, "bbs_call", "")).strip()
            if not connect_call:
                raise RuntimeError("Send/Receive: BBS connect_call not configured")

            path_via = (getattr(bbs, "path_via", "") or "").strip()
            tnc_connect_cmd = (iface.data.get("tnc_connect_cmd") or "C").strip()

            if path_type in ("DIRECT", ""):
                connect_cmd = f"{tnc_connect_cmd} {connect_call}"

            elif path_type in ("VIA", ""):
                vias = [v.strip().upper() for v in re.split(r"[,\s]+", path_via) if v.strip()]
                if not vias:
                    raise RuntimeError("Send/Receive: Path type is VIA digipeaters, but no via list is configured")
                connect_cmd = f"{tnc_connect_cmd} {connect_call} via {','.join(vias)}"

            else:
                raise RuntimeError(f"Send/Receive: Unknown path_type '{path_type}'")

            self._log(f"Connecting to BBS: {connect_cmd}")
            self._adapter.send_line(connect_cmd)

        # ------------------------------------------------------------
        # 5) Wait for BBS prompt OR TNC failure indications
        # ------------------------------------------------------------
        # 260104, handle TNC ***<error> occurrances
        bbs_prompt = (getattr(bbs, "command_prompt", None) or ">").strip()

        # If it is not a connect, it is one of these errors.
        # These live in InterfaceProfile.data (the JSON dict)
        # best place to see this:  'ui.interface_setup_widget.py'
        tnc_disconnect = (iface.data.get("tnc_disconnect_prompt") or "").strip()
        tnc_timeout    = (iface.data.get("tnc_timeout_prompt") or "").strip()

        # Regex-safe literals (critical for strings containing '*', '[', etc.)
        bbs_pat, _prompt_ci = self._get_bbs_prompt_pattern(snap, fallback_prompt=bbs_prompt)

        fail_pats: list[str] = []
        if tnc_disconnect:
            fail_pats.append(re.escape(tnc_disconnect))
        if tnc_timeout:
            fail_pats.append(re.escape(tnc_timeout))

        # Optional: add robust fallbacks if the user hasn't configured prompts
        # (these won't hurt even if the configured ones exist)
        fail_pats.extend([
            r"\*\*\*.*retry count exceeded",
            r"\*\*\*.*disconn",  # matches DISCONNECTED / Disconnect / etc.
        ])

        patterns = [bbs_pat] + fail_pats

        # Choose a connect timeout that's realistic for RF connects
        timeout = float(getattr(bbs, "command_timeout", 15.0) or 15.0)
        timeout = max(timeout, float(iface.data.get("remote_timeout") or 0) or 0, 60.0)

        self._log(f"Waiting for BBS prompt '{bbs_prompt}' (or TNC failure), timeout={timeout:.1f}s")
        # matched = self._adapter.expect_any_match(patterns, timeout=timeout)
        matched = self._wait_for_any_or_abort(
            patterns=patterns,
            success_pattern=bbs_pat,
            timeout=timeout,
            context=f"waiting for BBS prompt '{bbs_prompt}' while connecting",
        )

        # Success (we saw the BBS prompt)
        self._log("BBS connected")

        #  Detect SID → bind spec
        sid = self._detect_sid_and_bind_spec(snap)

        self._log("BBS connected")

        # ------------------------------------------------------------
        # 6) BBS init commands (BEFORE): run after connect, before other BBS commands (260129)
        # ------------------------------------------------------------
        try:
            use_init = bool(getattr(bbs, "use_init_cmd", False))
        except Exception:
            use_init = False

        ### CONFIRMED: self._log(f">>>>> bbs.command_prompt={bbs.command_prompt}")
        if use_init:
            raw = (getattr(bbs, "cmd_before", "") or "")
            for line in raw.splitlines():
                # allow ';' on a line to separate multiple commands
                for part in [p.strip() for p in line.split(";") if p.strip()]:
                    if self._stop_requested():
                        self._log("Send/Receive: cancel requested during BBS init(before)")
                        return
                    self._log(f"BBS init(before): {part}")
                    self._send_and_wait(part, bbs.command_prompt)
        else:
            # optional: keep quiet, or log once for visibility
            self._log("BBS init(before): skipped (use_init_cmd is False)")

        # ------------------------------------------------------------
        
    def _kick_tnc_to_cmd_mode(self, tnc_prompt: str) -> None:
        """
        Attempt to return the TNC to command mode (best-effort).
        
        Tactics: send CR, then Ctrl-C, then 'D' (disconnect), then wait for prompt.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._kick_tnc_to_cmd_mode")

        # 1) Gentle wake-up: CR
        self._adapter.send_line("")  # sends just CR

        try:
            self._adapter.expect(tnc_prompt, timeout=1.0)
            return
        except TimeoutError:
            pass

        # 2) Try Ctrl-C (0x03) to break out of a connected BBS
        if hasattr(self._conn, "write"):
            self._conn.write(b"\x03")  # Ctrl-C
        else:
            # fallback: best-effort, send as text (some transports may pass it)
            self._adapter.send_line("\x03")

        time.sleep(0.10)  # 100ms pause like Outpost Classic

        # 3) Force Disconnect in case we're in a connected state
        self._adapter.send_line("D")

        # 4) Now wait for cmd prompt
        self._adapter.expect(tnc_prompt, timeout=5.0)


    # 260103, put the TNC in a known state
    def _prepare_tnc_known_state(self, snap: SessionSnapshot, tnc_prompt: str) -> None:
        """
        Put the TNC into a known, safe command-mode state before any BBS commands.

        This is NOT user-configured init commands; it is OutpostX's required preflight.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._prepare_tnc_known_state")

        if self._stop_requested():
            return

        iface = getattr(snap, "interface", None)
        station = getattr(snap, "station", None)

        # Must have an interface profile to proceed
        if iface is None:
            self._log("WARNING: No active interface profile; skipping TNC preflight")
            return

        # 4) Send a harmless command to confirm we're really at cmd prompt
        if self._stop_requested():          # 260226  If aborted, then exit
            return
        self._send_to_tnc_and_wait_prompt("B", tnc_prompt)   # any safe cmd is fine

        # 6) Echo on (make configurable later)
        if self._stop_requested():          # 260226  If aborted, then exit
            return
        self._send_to_tnc_and_wait_prompt("ECHO ON", tnc_prompt)

        # 7) Set MYCALL from active legal call sign
        iface_data = getattr(iface, "data", None)
        if not isinstance(iface_data, dict):
            iface_data = {}

        # Debug visibility (remove later if you want)
        #try:
        #    self._log(f"DEBUG iface.data keys: {sorted(iface_data.keys())}")
        #    self._log(f"DEBUG iface.data['tnc_mycall_cmd']: {iface_data.get('tnc_mycall_cmd')!r}")
        #except Exception:
        #    pass

        mycall_cmd = (str(iface_data.get("tnc_mycall_cmd", "")) or "").strip()
        if not mycall_cmd:
            # Optional legacy alias
            mycall_cmd = (str(iface_data.get("mycall_cmd", "")) or "").strip()

        if not mycall_cmd:
            self._log("WARNING: InterfaceProfile.data['tnc_mycall_cmd'] is empty; skipping MYCALL set")
            return

        # deal with a leagl_call_sign or a tactical_call_sign
        session_mycall = self._resolve_session_mycall(snap)

        if self._stop_requested():
            return

        self._send_to_tnc_and_wait_prompt(f"{mycall_cmd} {session_mycall}", tnc_prompt)
        self._log(f"TNC MYCALL set to {session_mycall}")


    def _login_bbs_via_telnet(self, snap: SessionSnapshot) -> None:

        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._login_bbs_via_telnet")

        from services.jnos_secure_login import check_jnos_secure_login
        from services.wl2k_secure_login import (
            is_wl2k_banner,
            extract_wl2k_challenge,
            build_outpostx_sid,
            build_wl2k_pr_line,
        )

        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")

        iface = snap.interface
        bbs = snap.bbs
        iface_data = getattr(iface, "data", {}) or {}
        ### self._log(f"****DEBUG: iface_data =\n{pformat(iface_data)}")

        login_prompt = (str(iface_data.get("telnet_logon_prompt", "")) or "").strip()
        password_prompt = (str(iface_data.get("telnet_password_prompt", "")) or "").strip()

        username = (getattr(bbs, "login_username", "") or "").strip()
        server_password = (getattr(bbs, "account_password", "") or "").strip()
        mailbox_password = (getattr(bbs, "access_password", "") or "").strip()

        rx_accum = ""

        try:
            rx_accum += self._adapter.drain_buffer() or ""
        except Exception:
            pass

        password_prompt_pat = password_prompt
        if password_prompt and password_prompt.lower() == "password":
            password_prompt_pat = r"Password(?:\s*\[[0-9A-Fa-f]{8}\])?\s*:"

        # ------------------------------------------------------------
        # 1) Wait for TELNET login prompt or password prompt
        # ------------------------------------------------------------
        self._log("Waiting for TELNET login prompt")
        matched = self._adapter.expect_any_match(
            [login_prompt, password_prompt_pat],
            timeout=15.0,
        )

        try:
            rx_accum += self._adapter.drain_buffer() or ""
        except Exception:
            pass

        # ------------------------------------------------------------
        # 2) Send username if needed, then wait for password prompt
        # ------------------------------------------------------------
        if matched == login_prompt:
            if not username:
                raise RuntimeError("TELNET username is not configured")

            self._log(f"TELNET login as '{username}'")
            self._adapter.send_line(username)

            self._adapter.expect(password_prompt_pat, timeout=10.0)

            try:
                rx_accum += self._adapter.drain_buffer() or ""
            except Exception:
                pass

        # ------------------------------------------------------------
        # 3) Send server-access password
        #
        # For normal TELNET/JNOS, this is the BBS password.
        # For Winlink, this is the first-stage server password
        # (e.g. CMSTELNET), not the mailbox challenge password.
        # ------------------------------------------------------------
        if server_password:
            password_to_send = check_jnos_secure_login(server_password, rx_accum)

            if password_to_send != server_password:
                self._log("TELNET login: secure password challenge detected; sending hashed response")
            else:
                self._log("TELNET login: sending server-access password")

            self._adapter.send_line(password_to_send)
        else:
            self._log("WARNING: TELNET server-access password is empty")

        # ------------------------------------------------------------
        # 4) After server password, actively look for either:
        #    - a WL2K secure-login challenge (;PQ: ########), or
        #    - a normal BBS prompt for non-WL2K systems
        # ------------------------------------------------------------
        wl2k_pq_pat = r";PQ:\s*[0-9A-Fa-f]{8}"
        bbs_prompt = getattr(bbs, "command_prompt", None) or ">"
        bbs_pat, _ci = self._get_bbs_prompt_pattern(snap, fallback_prompt=bbs_prompt)

        path_type = (getattr(bbs, "path_type", "") or "DIRECT").strip().upper()

        wl2k_pq_pat = r";PQ:\s*[0-9A-Fa-f]{8}"
        bbs_prompt = getattr(bbs, "command_prompt", None) or ">"
        bbs_pat, _ci = self._get_bbs_prompt_pattern(snap, fallback_prompt=bbs_prompt)

        self._log("TELNET login: waiting for post-password response")

        if path_type == "NODE":
            # BPQ/front-end TELNET case:
            # after password, we may only be at the TELNET server menu,
            # not yet at the BBS prompt. Give bytes a chance to arrive,
            # but do not require a BBS prompt before running the script.
            try:
                self._adapter.wait_quiet(quiet_seconds=0.50, timeout=3.0)
            except Exception:
                pass

            try:
                rx_accum += self._adapter.drain_buffer() or ""
            except Exception:
                pass

            matched = None

        else:
            matched = self._adapter.expect_any_match(
                [wl2k_pq_pat, bbs_pat],
                timeout=15.0,
            )

            try:
                rx_accum += self._adapter.drain_buffer() or ""
            except Exception:
                pass

        # ------------------------------------------------------------
        # 5) Winlink secure-login branch
        #    Use access_password for the ;PQ: -> ;PR: response.
        #
        # Important:
        #   WL2K sends the prompt (CMS>) immediately after ;PQ:.
        #   Outpost then sends:
        #       [OUTPOSTX-26.04.0]
        #       ;PR: ########
        #   and proceeds directly into the next command flow (typically LM).
        #   We do NOT wait for another CMS> after sending ;PR:.
        # ------------------------------------------------------------
        if matched == wl2k_pq_pat or is_wl2k_banner(rx_accum):
            challenge = extract_wl2k_challenge(rx_accum)
            if not challenge:
                raise RuntimeError(
                    "WL2K challenge prompt was detected, but no ';PQ:' value could be extracted"
                )

            if not mailbox_password:
                raise RuntimeError(
                    "WL2K secure logon required, but access_password is not configured"
                )

            # Winlink sends CMS> immediately after ;PQ:
            if "CMS>" not in rx_accum:
                self._log("WL2K secure login: waiting for CMS> after ;PQ:")
                self._adapter.expect(re.escape("CMS>"), timeout=10.0)
                try:
                    rx_accum += self._adapter.drain_buffer() or ""
                except Exception:
                    pass

            sid_line = build_outpostx_sid("26.04.0")
            pr_line = build_wl2k_pr_line(challenge, mailbox_password)

            self._adapter.send_line(sid_line)

            self._adapter.send_line(pr_line)

            self._log("WL2K secure login complete")
            self._log("BBS connected")

            self._detect_sid_and_bind_spec(snap, banner=rx_accum)
            return

        # ------------------------------------------------------------
        # 6) Normal TELNET path (non-WL2K)
        #
        # At this point, all TELNET/BBS authentication is complete.
        # For most systems (e.g. JNOS), we are already at the BBS prompt.
        # For front-end TELNET servers (e.g. BPQ), SCRIPT/NODE mode may be
        # required to enter the actual BBS before SID detection.
        # ------------------------------------------------------------
        path_type = (getattr(bbs, "path_type", "") or "DIRECT").strip().upper()

        if path_type == "NODE":
            self._log("TELNET login complete; running path script before SID detection")

            # Clean up any front-end banner/menu text before starting the script.
            try:
                self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
            except Exception:
                pass

            # discard TELNET front-end banner / menu text
            try:
                self._adapter.drain_buffer()
            except Exception:
                pass

            rx_accum = ""
            self._run_path_script_if_needed(snap)

            # After the path script, collect the BBS banner/prompt text that
            # arrived as a result of the script so SID detection sees the
            # actual BBS, not the TELNET front-end.
            self._log("Waiting for BBS prompt after TELNET path")

            bbs_prompt = getattr(bbs, "command_prompt", None) or ">"
            bbs_pat, _ci = self._get_bbs_prompt_pattern(snap, fallback_prompt=bbs_prompt)

            self._wait_for_any_or_abort(
                patterns=[bbs_pat],
                success_pattern=bbs_pat,
                timeout=15.0,
                context="waiting for BBS prompt after TELNET path",
            )

            try:
                self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
            except Exception:
                pass

            try:
                rx_accum += self._adapter.drain_buffer() or ""
            except Exception:
                pass

        else:
            self._log("Waiting for BBS prompt after TELNET login")

            try:
                rx_accum += self._adapter.drain_buffer() or ""
            except Exception:
                pass

        self._log("BBS connected")
        self._detect_sid_and_bind_spec(snap, banner=rx_accum)

    # -------------------------------------    
    def _login_bbs_via_agwpe(self, snap: SessionSnapshot) -> None:
        """
        260408
        Drive AGWPE login/registration/BBS connect.

        Sequence:
        1) optional AGWPE remote logon
        2) register our callsign
        3) connect direct or via
        4) wait for BBS prompt
        5) detect SID and bind spec
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._login_bbs_via_agwpe")

        if self._stop_requested():
            raise SessionAbortRequested("Operator aborted session")

        if not self._adapter or not self._conn:
            raise RuntimeError("SendReceiveSession: adapter/connection not initialized")

        iface = snap.interface
        bbs = snap.bbs
        data = getattr(iface, "data", {}) or {}

        # Strongly typed access to AGW transport
        conn = self._conn

        # ----------------------------
        # 1) Optional AGWPE remote logon
        # ----------------------------
        agw_logon_required = bool(data.get("agw_logon_required", False))
        agw_logon = (str(data.get("agw_logon", "")) or "").strip()
        agw_password = (str(data.get("agw_password", "")) or "").strip()

        if agw_logon_required:
            self._log("AGWPE: sending remote logon")
            if not agw_logon:
                raise RuntimeError("AGWPE logon_required is True but agw_logon is blank")

            conn.set_login(agw_logon)
            conn.set_password(agw_password)
            conn.send_login()
            # IRS says no explicit success/failure reply is returned
            time.sleep(0.25)

        # ----------------------------
        # 2) Register our callsign
        # ----------------------------
        my_call = self._resolve_session_mycall(snap)

        conn.set_call_from(my_call)

        self._log(f"AGWPE: registering {my_call}")
        conn.is_registered = False
        conn.register()

        if hasattr(conn, "wait_for_registration"):
            ok = conn.wait_for_registration(timeout=5.0)
        else:
            time.sleep(0.75)
            ok = bool(getattr(conn, "is_registered", False))

        if not ok:
            raise RuntimeError(
                f"AGWPE registration failed for {my_call}. "
                "That callsign may already be in use by AGWPE or another application."
            )

        self._log(f"AGWPE: registered {my_call}")

        # ----------------------------
        # 3) Set radio port + destination + connect
        # ----------------------------
        radio_port_s = (str(data.get("agw_radio_port", "")) or "").strip()
        try:
            radio_port = int(radio_port_s) if radio_port_s else 1
        except ValueError:
            radio_port = 1
        conn.set_radio_port(radio_port)

        connect_call = (getattr(bbs, "connect_call", None) or getattr(bbs, "bbs_call", "")).strip().upper()
        if not connect_call:
            raise RuntimeError("Send/Receive: BBS connect_call not configured")

        conn.set_call_to(connect_call)

        path_type = (getattr(bbs, "path_type", "") or "DIRECT").strip().upper()
        path_via = (getattr(bbs, "path_via", "") or "").strip()

        # Optional cleanup before waiting on fresh connection text
        try:
            self._adapter.wait_quiet(quiet_seconds=0.20, timeout=1.0)
        except Exception:
            pass
        self._adapter.drain_buffer()

        if path_type in ("DIRECT", ""):
            self._log(f"AGWPE: connecting direct to {connect_call} on radio port {radio_port}")
            conn.bbs_connect()

        elif path_type in ("VIA", "VIA_DIGIS", "VIA_DIGIPEATER", "VIA_DIGIPEATERS"):
            vias = [v.strip().upper() for v in re.split(r"[,\s]+", path_via) if v.strip()]
            if not vias:
                raise RuntimeError("Send/Receive: Path type is VIA digipeaters, but no via list is configured")

            self._log(f"AGWPE: connecting to {connect_call} via {','.join(vias)} on radio port {radio_port}")
            conn.set_via(vias)
            conn.bbs_connect_via()

        elif path_type in ("KANODE", "KA-NODE", "NETROM", "KA_NODE_NETROM"):
            raise NotImplementedError("KA-Node / NETROM access is not implemented yet for AGWPE")

        else:
            raise RuntimeError(f"Send/Receive: Unknown path_type '{path_type}'")

        # ----------------------------
        # 4) Wait for BBS prompt OR failure
        # ----------------------------
        bbs_prompt = (getattr(bbs, "command_prompt", None) or ">").strip()
        bbs_pat, _prompt_ci = self._get_bbs_prompt_pattern(snap, fallback_prompt=bbs_prompt)

        patterns = [
            bbs_pat,
            r"\*\*\* CONNECTED .*",     # AGWPE connection message
            r"\*\*\* DISCONNECTED.*",
            r"RETRYOUT",
        ]

        timeout = float(getattr(bbs, "command_timeout", 15.0) or 15.0)
        timeout = max(timeout, 30.0)

        self._log(f"AGWPE: waiting for BBS prompt '{bbs_prompt}', timeout={timeout:.1f}s")

        end = time.time() + timeout
        saw_connect = False

        while time.time() < end:
            self._check_stop_and_abort()

            try:
                matched = self._adapter.expect_any_match(patterns, timeout=1.0)
            except TimeoutError:
                continue

            if matched == bbs_pat:
                break

            if matched == r"\*\*\* CONNECTED .*":
                saw_connect = True
                continue

            tail = self._adapter.drain_buffer() or ""
            raise RuntimeError(
                "AGWPE connect failed before BBS prompt. "
                f"matched={matched!r}. Last RX:\n{tail[-600:]}"
            )
        else:
            tail = self._adapter.drain_buffer() or ""
            raise RuntimeError(
                f"Timeout waiting for AGWPE/BBS prompt '{bbs_prompt}'. "
                f"saw_connect={saw_connect}. Last RX:\n{tail[-600:]}"
            )

        self._log("BBS connected")

        # ----------------------------
        # 5) Detect SID -> bind spec
        # ----------------------------
        try:
            self._adapter.wait_quiet(quiet_seconds=0.20, timeout=1.0)
        except Exception:
            pass

        banner = self._adapter.drain_buffer() or ""
        self._detect_sid_and_bind_spec(snap, banner=banner)

    # -------------------------------------    
    def _detect_sid_and_bind_spec(
        self,
        snap: SessionSnapshot,
        banner: str | None = None,
    ) -> object | None:
        """
        Detect a BBS SID from banner text and bind the matching BBS spec.

        Args:
            snap:
                Active session snapshot.
            banner:
                Optional banner text already captured by the caller.
                If omitted, this method drains the adapter buffer.

        Returns:
            The parsed SID object if detected, otherwise None.

        Raises:
            RuntimeError:
                If WL2K is detected (not yet supported), or if spec loading/binding fails.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._detect_sid_and_bind_spec")

        bbs = getattr(snap, "bbs", None)

        if banner is None:
            if not self._adapter:
                raise RuntimeError("SendReceiveSession: adapter not initialized")
            banner = self._adapter.drain_buffer() or ""

        sid = parse_sid(banner)     # access: services.bbs_protocol_adapter


        # Optional debug while you are still stabilizing login paths
        ### self._log(f"***DEBUG[detect_sid] sid={sid};  banner_tail={banner[-200:]!r}")

        if not sid:
            self._log("WARNING: No SID detected; continuing without spec (parsing may be limited).")
            return None

        self._log(f"Detected BBS SID {sid.sid_raw} (type {sid.sid_type})")

        ## if sid.sid_type == "WL2K":
        ##     self._log("Detected WL2K SID; continuing without binding a WL2K spec yet")
        ##     return sid
            
        try:
            spec = self._spec_loader.load_for_sid_type(sid.sid_type)
            if hasattr(bbs, "bind_spec"):
                bbs.bind_spec(spec)
            self._log(f"Using BBS spec '{spec.id}' from {spec.source_path}")
        except Exception as e:
            self._log(f"ERROR: Failed to load/bind spec for SID type {sid.sid_type}: {e}")
            raise

        return sid


    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------
    # Message Identity Consistency (do not “simplify” back to string checks)
    #
    # OutpostX treats IDs as the authoritative identity; callsigns are display
    # / legacy / human-friendly fields and can be ambiguous.
    #
    # Identity rules for send eligibility:
    #   - Station identity: compare by station_profile_id (preferred)
    #       msg.station_profile_id == snap.station.station_id (or snap.station.id)
    #
    #   - BBS identity: compare by bbs_profile_id (preferred)
    #       msg.bbs_profile_id == snap.bbs.profile_id (or underlying BBSProfile.id)
    #
    # Operational safety checks (secondary, still useful):
    #   - from_call text must match active legal call (prevents “loose FROM” sends)
    #   - bbs_call/connect_call text must match active BBS call (prevents cross-BBS sends)
    #
    # Why IDs matter:
    #   - Callsigns can be reformatted, aliased, or changed (connect_call vs bbs_call).
    #   - Friendly names are not unique.
    #   - Future features (multi-station, multi-BBS queues, templates) require stable keys.
    # ------------------------------------------------------------------
    def _send_outbound(self, snap: SessionSnapshot) -> None:
        """
        Send queued outbound messages that are eligible for this session.

        Rules:
          1) Status = QUEUED  (handled by query)
          2) Folder = Outbox
          3) FROM matches Active Station ID
          4) BBS matches Active BBS

        if/when IDs exist in the Message schema, they are authoritative; string comparisons 
        are secondary safety checks only.  
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._send_outbound")

        if self._stop_requested():          # 260226  If aborted, then exit
            raise SessionAbortRequested("Operator aborted session")

        queued = self._message_repo.find_by_state("QUEUED", direction="OUTBOUND", limit=100)
        # print(f"DEBUG: SendReceiveSession._send_outbound.queued = {queued}")

        if not queued:
            self._log("No outbound messages queued")
            return

        
        ### print(f">>>DEBUG: SendReceiveSession._send_oiutbound.snap={snap!r}, station={getattr(snap, 'station', None)!r}")

        # Resolve session context
        active_from = (self._system_config.get_default_from_call() or "").strip().upper()
        # 260111, prevents “loose from calls trigger a send”
        if not active_from:
            self._log("WARNING: No active Station legal call; refusing to send queued Outbox messages.")
            return

        # Active BBS call: prefer connect_call if you store it there; otherwise bbs_call
        active_bbs = (
            (getattr(snap.bbs, "connect_call", None) or "").strip()
            or (getattr(snap.bbs, "bbs_call", None) or "").strip()
        ).upper()
        # 260111, prevents cross-bbs accidental sends
        if not active_bbs:
            self._log("WARNING: No active BBS selected; refusing to send queued Outbox messages.")
            return

        # 260111; Outbox folder idx (single source of truth)
        cfg = getattr(self._message_repo, "cfg", None)
        outbox_idx = getattr(cfg, "default_outbound_folderidx", None) if cfg else None

        if outbox_idx is None:
            self._log("WARNING: Outbox folderidx is not configured; cannot determine send eligibility.")
            return

        # continue
        eligible: list[tuple[object, object]] = []
        for msg, body in queued:
            msg_from = (getattr(msg, "from_call", "") or "").strip().upper()
            msg_bbs = (getattr(msg, "bbs_call", "") or "").strip().upper()
            msg_folder = getattr(msg, "folderidx", None)

            if self.trace:
                self._log(f"TRACE: SRS._send_outbound: msg_from  ={msg_from}; active_from ={active_from}")
                self._log(f"TRACE: SRS._send_outbound: msg_bbs   ={msg_bbs};  active_bbs  ={active_bbs}")
                self._log(f"TRACE: SRS._send_outbound: msg_folder={msg_folder}; active_bbs={outbox_idx}")

            # Only send from Outbox
            if msg_folder != outbox_idx:
                continue

            # FROM must match active station
            if msg_from != active_from:
                continue

            # BBS must match active BBS
            if msg_bbs != active_bbs:
                continue

            eligible.append((msg, body))

        self._log(f"Sending {len(eligible)} outbound message(s) (eligible of {len(queued)} queued)")

        if not eligible:
            self._log("No outbound messages eligible for this session (BBS/Station/Outbox filters)")
            return

        for msg, body in eligible:
            if self._stop_requested():
                self._log("Send/Receive: cancel requested (stopping outbound loop)")
                break
            self._send_message(msg, body, snap)


    def _send_message(self, msg, body, snap) -> None:
        """
        Send a single outbound message to the connected BBS (one-shot block transmit).

        Wire sequence (no intermediate prompt required):
          1) SP/S <TOCALL>
          2) <SUBJECT>
          3) message body lines...
          4) /EX
          5) Wait for BBS prompt (success) OR known TNC failure strings (disconnect/timeout/retry exceeded)

        Notes:
          - This method assumes the session is already connected to the target BBS.
          - It is conservative about prompts and uses regex-safe matching for failure strings.
        """

        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._send_message")

        if self._stop_requested():          # 260226  If aborted, then exit
            return

        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")

        msgid = getattr(msg, "msgidx", None) or getattr(msg, "id", None)
        self._log(f"Sending message msgidx={msgid}")

        bbs = snap.bbs
        iface = snap.interface

        # ----------------------------
        # Resolve interface failure prompts (from InterfaceProfile.data)
        # ----------------------------
        tnc_disconnect = ""
        tnc_timeout = ""
        tnc_cmd_prompt = "cmd:"
        if iface is not None:
            data = getattr(iface, "data", None)
            if isinstance(data, dict):
                tnc_disconnect = (data.get("tnc_disconnect_prompt") or "").strip()
                tnc_timeout = (data.get("tnc_timeout_prompt") or "").strip()
                tnc_cmd_prompt = (data.get("tnc_cmd_prompt") or tnc_cmd_prompt).strip()
            else:
                # fallback (older interface models)
                tnc_cmd_prompt = (getattr(iface, "tnc_cmd_prompt", None) or tnc_cmd_prompt).strip()

        # ----------------------------
        # Build send command token + TOCALL (subject sent on its own line)
        # ----------------------------
        to_call = (getattr(msg, "to_call", None) or getattr(msg, "to", None) or "").strip()
        if not to_call:
            raise RuntimeError(f"SendReceiveSession: outbound msgidx={msgid} has no TO call")

        subject = (getattr(msg, "subject", "") or "").strip()

        send_blocks = build_send_blocks(bbs, msg)

        # ----------------------------
        # Extract body text (MessageBody.message in your schema)
        # ----------------------------
        body_text = ""
        if body is not None:
            body_text = (
                getattr(body, "body_text", None)
                or getattr(body, "text", None)
                or getattr(body, "body", None)
                or getattr(body, "message", None)  # IMPORTANT for your MessageBody model
                or ""
            )

        if not body_text:
            body_text = (
                getattr(msg, "body_text", None)
                or getattr(msg, "body", None)
                or ""
            )

        # Insert any tags into the message body
        body_text = str(body_text)

        # Apply Outpost wire-format tags only at transmit time.
        # Stored message body remains unchanged.
        body_text = self._apply_outbound_wire_tags(msg, body_text)

        # Normalize newlines; send line-by-line without embedded \r
        body_lines = body_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        # End-of-message marker
        eom = (getattr(bbs, "end_of_message", None) or "/EX").strip()

        # ----------------------------
        # Transmit as a single "block" (no waiting for intermediate prompts)
        # ----------------------------
        # 260520
        done_prompt = (getattr(bbs, "command_prompt", None) or ">").strip()

        for block in send_blocks:
            tx_lines = [block.command_line]
            tx_lines.extend(block.extra_address_lines)

            if subject:
                tx_lines.append(subject)

            tx_lines.extend(body_lines)
            tx_lines.append(eom)

            self._log(f"TX: {block.command_line}")
            for extra in block.extra_address_lines:
                self._log(f"TX: {extra}")

            if subject:
                self._log(f"TX: {subject}")

            self._log(f"TX: <{len(body_lines)} body line(s)>")
            self._log(f"TX: {eom}")

            for line in tx_lines:
                if self._stop_requested():
                    self._log("Send/Receive: cancel requested (stopping message send)")
                    return
                self._adapter.send_line(line)

            self._wait_for_prompt_or_abort(done_prompt=done_prompt, snap=snap, poll_timeout=1.0)
            self._adapter.drain_buffer()


        # If we got here, we saw the BBS prompt (success).
        # ----------------------------
        # Mark SENT and move to Sent
        # ----------------------------
        if msgid is not None:
            try:
                updated = self._message_repo.mark_sent(int(msgid))
                ### self._log(f"***DEBUG: mark_sent(msgidx={msgid}) -> {updated}")

                self._auto_print_sent_message(
                    snap=snap,
                    msgidx=int(msgid),
                )

                moved = self._message_repo.move_to_sent(int(msgid))
                ### self._log(f"***DEBUG: move_to_sent(msgidx={msgid}) -> {moved}")

                if moved == 0:
                    self._log("***WARNING: Sent folder not found (root folder name must be exactly 'Sent'); message left in current folder.")

            except Exception as exc:
                self._log(f"***WARNING: could not mark SENT/move to Sent for msgidx={msgid}: {exc}")


    # ------------------------------------------------------------------
    # Inbound
    # ------------------------------------------------------------------
    def _receive_inbound(self, snap: SessionSnapshot) -> None:
        """
        Receive inbound messages from the BBS.

        Flow:
          1) List messages (LM/LB/etc)
          2) Parse IDs from listing
          3) For each ID not already in DB, retrieve full message (R <id>)
          4) Parse and store inbound (idempotent)

        Notes:
         - Uses MessageRepository.inbound_exists_for_dedupe() for unified inbound skip-check.
         - This centralizes dedupe logic for both:
            • Standard BBSs (locator match: bbs_call + bbsmsgno)
            • JNOS BBSs (listing fingerprint match)
        """
        if self._stop_requested():          # 260226  If aborted, then exit
            raise SessionAbortRequested("Operator aborted session")

        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")


        # ------------------------------------------------------------
        # Set up some common variables for the inbound run
        # ------------------------------------------------------------
        received_new_count = 0


        # --------
        # RETRIEVE THE spec_id = BBS TYPE and this bbs_call
        # --------
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._receive_inbound")

        bbs = snap.bbs
        spec_id = str(getattr(getattr(bbs, "_spec", None), "raw", {}).get("id", "")).lower()
        ### CONFIRMED: self._log(f">>>>> SPEC_ID, spec_id={spec_id}")
        
        # Best-effort BBS locator for dedupe
        bbs_call = (
            getattr(bbs, "bbs_call", None)
            or getattr(bbs, "call", None)
            or getattr(bbs, "callsign", None)
            or ""
        )

        # ------------------------------------------------------------
        # Operator calls (used to filter listing rows before R #)
        # Classic Outpost behavior: only retrieve messages addressed to us.
        # 260113
        # ------------------------------------------------------------
        my_calls: set[str] = set()
        st = getattr(snap, "station", None)
        ta = getattr(snap, "tactical", None)

        if st and getattr(st, "legal_call_sign", ""):
            my_calls.add(st.legal_call_sign.strip().upper())
        if ta and getattr(ta, "tactical_call_sign", ""):
            my_calls.add(ta.tactical_call_sign.strip().upper())

        # ------------------------------------------------------------
        # Determine which categories are enabled (PRIVATE/BULLETIN/NTS)
        # ------------------------------------------------------------
        enabled = []
        get_enabled = getattr(bbs, "enabled_categories", None)
        if callable(get_enabled):
            enabled = get_enabled() or []
        else:
            # fallback (shouldn't happen if you added enabled_categories)
            if bool(getattr(bbs, "retrieve_private", False)):
                enabled.append("PRIVATE")
            if bool(getattr(bbs, "retrieve_bulletins", False)):
                enabled.append("BULLETIN")
            if bool(getattr(bbs, "retrieve_nts", False)):
                enabled.append("NTS")

        if not enabled:
            self._log("No inbound categories enabled (Private/Bulletin/NTS); skipping receive.")
            return
        
        # ------------------------------------------------------------
        # Pre-compute Regex prompt pattern once for this receive pass.
        # Used to strip trailing "(#n) >" after each R <id>.
        # read_prompt_pat = Regex pattern
        # falback_prompt is teh same as read_prompt_pat... need to optimize
        # ------------------------------------------------------------
        fallback_prompt = (getattr(bbs, "command_prompt", None) or ">").strip() or ">"
        read_prompt_pat, read_prompt_ci = self._get_bbs_prompt_pattern(
            snap,
            fallback_prompt=fallback_prompt,
        )


        # ------------------------------------------------------------
        # HELPER ROUTINES: run list command for a category and return eligible msg ids
        # ------------------------------------------------------------
        
        def compute_jnos_synth_bbsmsgno(lm_row: dict, area_hint: str) -> str:
            """
            This is a general purpose function to generate a synthetic 'bbsmsgno' for JNOS.

            BACKGROUND
            For non-JNOS BBSs, the BBS plus the Msg Number form a unique combination for 
            a given message. For JNOS, that does not work since the Msg Number is relative 
            to the mail box (area) that you happen to be in.

            Build an equivalent bbsmsgno by to concatenating various List fields together and 
            then apply a HASH.

            NOTE
            JNOS message numbers are relative and change between sessions.
            We must compute a stable synthetic bbsmsgno from the LM row BEFORE
            dedupe and reuse that same value when storing the message.
            """
            if self.trace: 
                self._log(f">>>>>TRACE -- SendReceiveSession.compute_jnos_synth_bbsmsgno")

            ### CONFIRMED: self._log(f">>>>> Entered compute_jnos_synth_bbsmsgno <<<<<")
            # get the appropriate fields for the synthetic JNOS bbsmsgno
            # ar = (area_hint or lm_row.get("to_call") or lm_row.get("to") or "").strip().upper()
            # sa = (lm_row.get("sent_at_normalized") or lm_row.get("sent_at") or "").strip()
            # tc = (lm_row.get("to") or lm_row.get("to_call") or "").strip().upper()
            # sz = str(lm_row.get("size") or lm_row.get("bytes") or "").strip()         # OMIT: NOT STABLE
            fc = (lm_row.get("from") or lm_row.get("from_call") or "").strip().upper()
            tc = (lm_row.get("to") or lm_row.get("to_call") or "").strip().upper()
            sj = " ".join((lm_row.get("subject") or "").strip().split()).replace("|", "/")
            dm = (lm_row.get("month") or "").strip().upper()
            dd = (lm_row.get("day") or "").strip().upper()

            # concatenate the fields
            # apply a hash, replace non-printable characters, shift string to upper case
            # and return a 16 character string (J...............)
            material = f"{fc}|{tc}|{dm}|{dd}|{sj}"
            ### self._log(f"***DEBUG[-1072] material = {material}")
            digest = hashlib.sha1(material.encode("utf-8", errors="replace")).hexdigest().upper()
            ### self._log(f"***DEBUG[-1074] digest = J{digest[:15]}")
            return "J" + digest[:15]

        def _list_ids_for_category(category: str) -> list[str]:

            if self.trace: 
                self._log(f">>>>>TRACE -- SendReceiveSession._list_ids_for_category")

            cat = (category or "").strip().upper()

            # ------------------------------------------------------------
            # Build list command(s)
            # ------------------------------------------------------------
            cmds: list[str] = []
            custom_script = False
            current_area_hint = ""

            if cat == "BULLETIN":
                mode = str(getattr(bbs, "retrieve_bulletins_mode", "") or "").strip().upper()
                # self._log(f"***DEBUG[SRS-1093]: mode = {mode}")
                # return    # and Stop
              
                if mode == "SELECTED":
                    # --------------------------------------------------------
                    # General filtered BBS Bulletin List Commands, does NOT apply to JNOS
                    # 
                    # Command is in the typical format 'L> <name>'
                    # selections are of the format 'RACES, EQUAKE, WX, HUMOUR'
                    # --------------------------------------------------------
                    base = str(getattr(bbs, "cmd_list_filtered", "") or "").strip()   # e.g. "L>"
                    raw_selected = str(getattr(bbs, "retrieve_selected", "") or "")

                    # tokens: allow comma/semicolon separated entries, normalize whitespace
                    tokens = []
                    for t in raw_selected.replace(";", ",").split(","):
                        t = t.strip()
                        if t:
                            tokens.append(t)

                    # build up the LIST command, e.g. 'L> EQUAKE'
                    if base and tokens:
                        cmds = [f"{base} {t}".strip() for t in tokens]  
                    else:
                        # Selected mode but nothing selected -> retrieve no bulletins
                        self._log("BULLETIN retrieve_selected is empty; skipping bulletin retrieval")
                        return []

                elif mode == "CUSTOM":
                    custom_script = True
                    # --------------------------------------------------------
                    # JNOS: Custom bulletin retrieval script.
                    #
                    # This supports mailbox/area selection before listing, e.g.:
                    #   A XSCEVENTS
                    #   LA
                    #   A XSCALL
                    #   L> CUP
                    #
                    # The script is expected to come from BBS preferences.
                    # We accept several attribute names to avoid tight coupling
                    # to the preferences dialog implementation.
                    # --------------------------------------------------------

                    # retrieve the entire custom script
                    script_text = str(getattr(bbs, "retrieve_custom", "") or "").strip()

                    if not script_text:
                        self._log("BULLETIN custom retrieval selected but retrieve_custom is empty; skipping")
                        return []

                    # get individual lines from the script
                    # skip lines that are commented out
                    cmds = []
                    for raw in script_text.splitlines():
                        line = (raw or "").strip()
                        if not line:
                            continue
                        if line.startswith("#") or line.startswith(";"):
                            continue
                        cmds.append(line)

                else:
                    # Non-selected bulletin modes fall back to normal list_command_for behavior
                    pass

            # Default: single-command path (PRIVATE/NTS, and BULLETIN non-SELECTED)
            if not cmds:
                cmd = None
                get_cmd = getattr(bbs, "list_command_for", None)

                if callable(get_cmd):
                    cmd = get_cmd(cat)
                else:
                    cmd = getattr(bbs, "list_messages_command", None) or "LM"

                cmd = str(cmd).strip()
                if not cmd:
                    return []
                cmds = [cmd]

            # ------------------------------------------------------------
            # Run list command(s), accumulate message ids
            # ------------------------------------------------------------
            ids: list[str] = []
            parse_rows = getattr(bbs, "parse_message_listing_rows", None)
            ### self._log(f"****DEBUG[1893]: parse_rows={parse_rows}")

            # Bulletin option: skip bulletins I sent (don’t download, don’t delete)
            skip_my_buls = False
            if cat == "BULLETIN":
                try:
                    skip_my_buls = bool(int(getattr(bbs, "skip_my_bulletins", 0) or 0))
                except Exception:
                    skip_my_buls = bool(getattr(bbs, "skip_my_bulletins", False))

            # for each accomulated command... 
            for cmd in cmds:
                cmd = str(cmd).strip()
                if not cmd:
                    continue

                # ------------------------------------------------------------
                # JNOS CUSTOM: change mailbox/area before listing
                # ------------------------------------------------------------
                if custom_script and cat == "BULLETIN":
                    up = cmd.upper()
                    ### CONFIRMED: self._log(f">>>>> DEBUG[-1427] cmd={cmd}, prompt={bbs.list_complete_prompt}")
                    if up.startswith("A "):
                        # Area/mailbox change (e.g. "A XSCEVENTS")
                        parts = cmd.split(None, 1)
                        if len(parts) == 2 and parts[1].strip():
                            current_area_hint = parts[1].strip().upper()

                        if self._stop_requested():          # 260226  If aborted, then exit
                            return

                        self._adapter.wait_quiet(quiet_seconds=0.50, timeout=6.0)
                        self._adapter.drain_buffer()
                        self._log(f"Selecting mailbox/area ({cmd})")

                        # ---------
                        # SEND JNOS CUSTOM BULLETIN AREA (A) CCOMMAND
                        # ---------
                        self._send_and_wait(cmd, bbs.list_complete_prompt)
                        self._adapter.drain_buffer()
                        continue

                # Quiet + clear buffer before list command
                self._adapter.wait_quiet(quiet_seconds=0.50, timeout=6.0)
                self._adapter.drain_buffer()

                if self._stop_requested():          # 260226  If aborted, then exit
                    return

                # ---------
                # SEND JNOS CUSTOM BULLETIN LIST CMD
                # ---------
                self._log(f"Retrieving {cat} message list ({cmd})")
                self._send_and_wait(cmd, bbs.list_complete_prompt)

                # ---------
                # RECOVER THE RESULTS OF THE LIST CMD
                # ---------
                listing = self._adapter.drain_buffer() or ""
                if not listing.strip():
                    self._log(f"WARNING: {cat} listing buffer is empty for ({cmd})")
                    continue

                # Normalize line endings before handing the text to spec-driven parsers.
                # WL2K currently comes back CR-delimited, not LF-delimited.
                listing_norm = listing.replace("\r\n", "\n").replace("\r", "\n")

                # ---------
                # READ EACH ROW
                # parse_rows(..) comes from the BBS spec file loader.  The json spec files (kpc3_spec.json, jnos_spec.json) 
                # and the code that loads those specs turns parser definitions into Python callables.
                # ---------
                if callable(parse_rows):
                    ### self._log(f"DEBUG[1966]: listing_norm = {listing_norm!r}")
                    rows = parse_rows(listing_norm) or []
                    ### self._log(f"DEBUG[1968]: spec_id={spec_id} cat={cat} rows={len(rows)}")

                    for r in rows:
                        ### self._log(f"WL2K DEBUG: parsed row = {r!r}")
                        if custom_script and cat == "BULLETIN" and current_area_hint:
                            # Stamp the area used for this list pass so JNOS dedupe can be precise.
                            r = dict(r)
                            r["area_hint"] = current_area_hint

                        msgno = str((r.get("msgno") or "")).strip()
                        if not msgno:
                            continue

                        # Per-category selection policy:
                        # - PRIVATE/NTS:    usually only if TO matches my_calls
                        # - WL2K exception: LM rows do not include a TO field; the mailbox itself
                        #                   is already scoped to the logged-in user, so accept PRIVATE/NTS rows.
                        # - BULLETIN:       selection depends on list command; no TO filter here

                        if cat in ("PRIVATE", "NTS"):
                            if spec_id != "wl2k":
                                to_field = str((r.get("to") or "")).strip()
                                if my_calls and not _to_matches_my_calls(to_field, my_calls):
                                    continue

                        # BULLETIN: skip my own bulletins if configured
                        if cat == "BULLETIN" and skip_my_buls:
                            from_field = str((r.get("from") or "")).strip()
                            # match like your other call compares (case-insensitive, ignore SSID nuances if needed)
                            if my_calls and any(from_field.upper() == c.upper() for c in my_calls):
                                continue

                        ids.append(msgno)
                        listing_row_by_id[msgno] = r
                else:
                    # Back-compat: only message numbers (no From/To filtering possible)
                    msg_ids = bbs.parse_message_listing(listing) or []
                    for mid in msg_ids:
                        s = str(mid).strip()
                        if s:
                            # In fallback mode we cannot enforce skip_my_bulletins without reading headers.
                            ids.append(s)

            # De-dupe, preserve order
            seen: set[str] = set()
            unique_ids: list[str] = []
            for m in ids:
                if m not in seen:
                    seen.add(m)
                    unique_ids.append(m)
            ids = unique_ids

            self._log(f"{cat} eligible: {len(ids)} message(s)")
            return ids

        def _to_matches_my_calls(to_field: str, my_calls: set[str]) -> bool:
            """
            Return True if the LM 'TO' field matches any of my calls.

            JNOS can present TO as:
              - CALL
              - CALL@domain (sometimes truncated in LM column)

            We treat these as a match if:
              - exact match on CALL, or
              - local-part before '@' matches CALL, or
              - startswith 'CALL@' (covers truncated domains)
            """
            if self.trace: 
                self._log(f">>>>>TRACE -- SendReceiveSession._to_matches_my_calls")

            if not my_calls:
                return False

            raw = (to_field or "").strip()
            if not raw:
                return False

            t = raw.upper()

            # Exact CALL match
            if t in my_calls:
                return True

            # Email-style: local-part match
            if "@" in t:
                local = t.split("@", 1)[0].strip()
                if local in my_calls:
                    return True

            # Truncated domain cases: "CALL@W1XSC.S" should match CALL
            for c in my_calls:
                if t.startswith(c + "@"):
                    return True
            return False

        def _retrieve_one_message(cat: str, msg_id: str, listing_row_by_id: dict[str, dict]) -> None:
            """ 260207
            Retrieve a single message by msg_id (R <id>), parse, store, and enqueue delete.
            This is the existing per-message retrieval code lifted out of the main loop so it can be
            reused by JNOS custom bulletin retrieval (mailbox-scoped).
            """
            # Use the 'received_new_count' variable from the calling _receive_inbound() function.
            nonlocal received_new_count

            if self.trace: 
                self._log(f">>>>>TRACE -- SendReceiveSession._retrieve_one_message")

            if self._stop_requested():          # 260226  If aborted, then exit
                return

            # ----------------------------
            # DEDUPE: Skip if already downloaded
            #   * JNOS:  create a hash of specific Lx fields for bbsmsgno
            #   * non-JNOS: use the BBS' original bbsmsgno 
            # The BBS_CALL plus the original or derived bbsmsgno is the unique combination
            # ----------------------------
            try:
                row = listing_row_by_id.get(str(msg_id), {})
                area_hint = (row.get("area_hint") or row.get("to") or "").strip().upper()
                ### self._log(f"***DEBUG[retrieve_one_-1560] row={row}")

                # -------------------------------
                # JNOS backfill: LM/LA row is the authoritative “bulletin area” context.
                # This prevents “unparsed inbound message” rows and stabilizes the JNOS locator.
                # -------------------------------

                # Get specific LM fields from the LM listing
                if spec_id == "jnos":
                    # row is from listing_row_by_id[str(msg_id)]
                    lm_to = (row.get("to") or "").strip()
                    lm_from = (row.get("from") or "").strip()
                    lm_mon = (row.get("month") or "").strip()
                    lm_day = (row.get("day") or "").strip()
                    lm_size = (row.get("size") or "").strip()
                    lm_subj = (row.get("subject") or "").strip()

                # For JNOS, create unique lookup dedupe bbsmsgno
                if spec_id == "jnos":
                    dedupe_bbsmsgno = compute_jnos_synth_bbsmsgno(lm_row=row, area_hint=area_hint)
                else:
                    dedupe_bbsmsgno = str(msg_id)
                    ### self._log(f"***DEBUG[retrieve_one-1582] dedupe_bbsmsgno='{dedupe_bbsmsgno}'")

                # Send both JNOS and non-JNOS LM listings through the dedupe process
                if self._message_repo.inbound_exists_for_dedupe(
                    bbs_id=spec_id,
                    bbs_call=bbs_call,
                    bbsmsgno=str(dedupe_bbsmsgno),
                    lm_row=row,
                    area_hint=area_hint,
                ):
                    self._log(f"Skipping already-downloaded message #{msg_id} (dedupe matched)")
                    return

            except Exception as e:
                self._log(f"WARNING: inbound dedupe check failed for #{msg_id}: {e}")

            # ----------------------------
            # Quiet + clear before each R #
            # Buffer Discipline:
            # Before LM and each R #, we quiet+drain so the listing/read capture contains
            # only the *new* response. This is critical at low baud and avoids “phantom”
            # prompt matches from late-arriving prior output.
            # ----------------------------
            self._adapter.wait_quiet(quiet_seconds=0.50, timeout=6.0)
            self._adapter.drain_buffer()
            add_local_mid = False

            self._log(f"Retrieving {cat} message #{msg_id}")
            try:
                if self._stop_requested():          # 260226  If aborted, then exit
                    return

                # ----------------------------
                # SEND THE 'Read <msg_id>' COMMAND
                # Retrieve the message string ('raw') in reply
                # ----------------------------
                self._send_and_wait(f"R {msg_id}", bbs.read_complete_prompt)

                raw = self._adapter.drain_buffer() or ""
                ### self._log(f"!! WL2K DEBUG: raw before strip = {raw!r}")

                # ------------------------------------------------------------
                # CLEAN UP THE RESULT
                # Strip the trailing prompt using the precomputed pattern
                # ------------------------------------------------------------
                ## self._log(f"***DEBUG: _receive...>rerieve_one_message: raw len before strip = {len(raw)} tail={raw[-80:]!r}")
                # This call always returns normalized LF text 
                raw = self._strip_trailing_prompt(
                    raw,
                    read_prompt_pat,
                    case_insensitive=read_prompt_ci,
                )
                ## self._log(f"***DEBUG: _receive...>rerieve_one_message: raw len after strip = {len(raw)} tail={raw[-80:]!r}")

                if not raw.strip():
                    self._log(f"WARNING: empty read for message #{msg_id}")
                    return      # or continue?

                # ------------------------------------------------------------
                # PARSE THE RETRIEVED MESSAGE INTO ITS PARTS
                # ------------------------------------------------------------
                # Line normalization (returning normalized LF text) happens in _strip_trailing_prompt(..)
                ### self._log(f"!!! WL2K DEBUG: raw after strip = {raw!r}")
                parsed = bbs.parse_full_message(raw)

                # 260208, tells us immediately why you ever got “(unparsed inbound message)”
                ### self._log(f"***DEBUG[SRS-1642] PARSED type={type(parsed)} keys={sorted(parsed.keys()) if isinstance(parsed, dict) else ''}")

                # -------------------------------
                # GET THE MESSAGE FIELDS READY FOR THE DB
                # -------------------------------
                if not isinstance(parsed, dict):
                    self._log(
                        f"ERROR: parse_full_message() returned {type(parsed).__name__}, "
                        f"expected dict for message #{msg_id}; skipping message."
                    )
                    return

                ###self._log(
                    f"***DEBUG[SRS-1423]  PARSED fields: from={parsed.get('from_call') or parsed.get('from')} "
                    f"to={parsed.get('to_call') or parsed.get('to')} "
                    f"subj={parsed.get('subject')} sent_at={parsed.get('sent_at')} bbsmsgno={parsed.get('bbsmsgno')}"
                ###)

                def _g(*keys, default=None):
                    """
                    A small local helper function used as a “get-first-available value” utility
                        * It takes multiple possible field names (*keys).
                        * It searches them in order inside the parsed dictionary.
                        * It returns the first one that exists and isn't empty.
                        * If none exist, it returns the default.
                    """        
                    for k in keys:
                        if k in parsed and parsed[k] not in (None, ""):
                            return parsed[k]
                    return default

                # Extract variables from 'parsed'
                body_text = _g("body", "body_text", "message", default="")
                # 260511 DEBUG
                self._log(f"***DEBUG RECEIPT: raw body head={repr(str(body_text)[:120])}")
                body_text, wire_flags = self._strip_inbound_wire_tags(str(body_text))   # strip any tags to the message
                header = _g("header", default=None)
                from_call = _g("from_call", "from", default="")
                to_call = _g("to_call", "to", default="")
                subject = _g("subject", default="")
                raw_sent_at = _g("sent_at", "sent_at_normalized", default=None)

                # WL2K backfill:  explicit WL2K backfill block
                # parse_full_message() currently gives us subject/from/to, but may not surface
                # Message ID / Date from the header into parsed['bbsmsgno'] / parsed['sent_at'].
                # The LM row is authoritative for both msg_id and date/time, so use it if needed.
                if spec_id == "wl2k":
                    if not raw_sent_at:
                        lm_date = (row.get("date") or "").strip()
                        lm_time = (row.get("time") or "").strip()
                        if lm_date and lm_time:
                            raw_sent_at = f"{lm_date} {lm_time}"
                        elif lm_date:
                            raw_sent_at = lm_date


                bbs_spec_raw = getattr(getattr(bbs, "_spec", None), "raw", {}) or {}
                sent_cfg = (bbs_spec_raw.get("sent_at", {}) or {})
                assume_tz = (sent_cfg.get("assume_timezone") or "utc").strip().lower()
                sent_at_normalized = _parse_bbs_datetime_to_iso(raw_sent_at, assume_timezone=assume_tz)


                recvmsgid = _g("recvmsgid", "messageid", default=None)
                parsed_bbs_call = (bbs_call or "").strip()

                # P132 - assign local MID to inbound message if enabled
                ms = getattr(snap, "message_settings", None)
                add_local_mid = bool(getattr(ms, "add_mid_to_inbound", False)) if ms else False

                if add_local_mid and not recvmsgid:
                    prefix = self._active_msg_id_prefix(snap)
                    cfg = getattr(self._system_config, "_config", None)

                    if prefix and cfg is not None:
                        recvmsgid = allocate_next_mid(cfg, prefix)

                # CONFIRMED: self._log(f"***DEBUG MID, add_local_mid={add_local_mid}, recvmsgid={recvmsgid}")


                # 260207
                # -------------------------------
                # JNOS backfill: LM/LA row is the authoritative “bulletin area” context.
                # This prevents “unparsed inbound message” rows and stabilizes the JNOS locator.
                # -------------------------------
                if spec_id == "jnos":
                     # TO: for JNOS bulletins is effectively the area (XSCPERM/XSCEVENTS/etc).
                    if not to_call and lm_to:
                        to_call = lm_to
                    if not from_call and lm_from:
                        from_call = lm_from
                    if not subject and lm_subj:
                        subject = lm_subj

                    # If we didn't get a sent_at from the R header, synthesize a stable sent_at from LM month/day.
                    # (Time is unknown; we set 00:00:00Z. Year is inferred in a “this year/last year” way.)
                    if not sent_at_normalized and lm_mon and lm_day:
                        try:
                            import datetime as _dt
                            mon_map = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}
                            mm = mon_map.get(lm_mon.strip()[:3].upper())
                            dd = int(str(lm_day).strip())
                            if mm and 1 <= dd <= 31:
                                now = _dt.datetime.utcnow().date()
                                y = now.year
                                cand = _dt.date(y, mm, dd)
                                if cand > now:
                                    cand = _dt.date(y - 1, mm, dd)
                                sent_at_normalized = f"{cand.isoformat()}T00:00:00Z"
                        except Exception:
                            pass

                # -----------------------------
                # PREPARE TO WRITE THE MSG TO THE DB 
                # Restore the bbsmsgno for either BBS types
                # -----------------------------
                orig_bbsmsgno = str(_g("bbsmsgno", "bbs_msg_no", default=msg_id))
                if spec_id == "jnos":
                    bbsmsgno = dedupe_bbsmsgno
                else:
                    bbsmsgno = orig_bbsmsgno

                # Check if the fields were actually populated.  If not, set a warning.
                has_meaning = any([
                    str(body_text).strip(),
                    str(subject).strip(),
                    str(from_call).strip(),
                    str(to_call).strip(),
                ])

                if not has_meaning:
                    self._log("WARNING: parsed fields empty; storing raw as body for safety")
                    body_text = raw
                    subject = subject or "(unparsed inbound message)"
                    header = header or ""

                # remove the <..> email brackets before saving
                from_call = self._normalize_email_address(from_call)
                to_call = self._normalize_email_address(to_call)

                ### self._log(f"WL2K DEBUG: raw_sent_at={raw_sent_at!r} sent_at_normalized={sent_at_normalized!r}")

                # Repository parameter remains named sent_at_iso for API compatibility.
                # Value may be UTC-Z or no-Z Local depending on what the BBS reported.     
                # And, write (Update/Insert) the message to the DB; updd: 260430
                # sent_at_normalized:
                # ISO-shaped BBS-reported message time.
                # May be UTC-Z if the BBS explicitly reported UTC, or no-Z Local if the BBS reported local time.

                inbound_msgidx = self._message_repo.upsert_inbound(
                    bbs_call=str(parsed_bbs_call),
                    bbsmsgno=str(bbsmsgno),
                    from_call=str(from_call),
                    to_call=str(to_call),
                    subject=str(subject),
                    header=header if header is None else str(header),
                    body_text=str(body_text),
                    sent_at_normalized=None if sent_at_normalized is None else str(sent_at_normalized),
                    recvmsgid=recvmsgid if recvmsgid is None else str(recvmsgid),
                    urgent=bool(_g("urgent", "is_urgent", default=False)) or wire_flags["is_urgent"],
                    encoded=bool(_g("encoded", "is_encoded", default=False)) or wire_flags["is_encoded"],
                    request_delivery_receipt=bool(_g("is_rdr", default=False)) or wire_flags["is_rdr"],                    
                    request_read_receipt=bool(_g("is_rrr", default=False)),
                )

                self._log(f"***DEBUG MID, Right after Upsert..., recvmsgid={recvmsgid}")


                request_dr = bool(_g("is_rdr", default=False)) or wire_flags["is_rdr"]
                # 260511 debug
                self._log(
                    f"***DEBUG RECEIPT: parsed_is_rdr={bool(_g('is_rdr', default=False))}, "
                    f"wire_is_rdr={wire_flags['is_rdr']}, request_dr={request_dr}"
                )

                if self._should_send_delivery_receipt(
                    category=cat,
                    from_call=str(from_call),
                    subject=str(subject),
                    request_delivery_receipt=request_dr,
                    snap=snap,
                ):
                    self._send_one_delivery_receipt(
                        to_call=str(from_call),
                        delivered_to=str(to_call),
                        original_subject=str(subject),
                        assigned_msg_id=str(recvmsgid or ""),
                        add_local_mid=bool(add_local_mid),
                        snap=snap,
                    )


                self._auto_print_received_message(
                    snap=snap,
                    msgidx=inbound_msgidx,
                    bbs_call=str(parsed_bbs_call),
                    from_call=str(from_call),
                    to_call=str(to_call),
                    subject=str(subject),
                    sent_at_normalized=None if sent_at_normalized is None else str(sent_at_normalized),
                    body_text=str(body_text),
                )

            except Exception as e:
                self._log(f"Receive canceled while reading message #{msg_id}: {e}")
                return  

            received_new_count += 1     # increment the counter for received messages


        def _delete_one_message(cat: str, msg_id: str) -> None:
            """ 260313
            Test CODE: replaces the delete queue.  Deletes should happen right after a successful retrieve
            Delete a single message by msg_id (R <id>). then report back.
            """
            if self.trace: 
                self._log(f">>>>>TRACE -- SendReceiveSession._delete_one_message")

            if self._stop_requested():          # 260226  If aborted, then exit
                return

            try:
                # Small pause + drain helps prevent left-over bytes
                # from contaminating prompt waits on slow RF links.
                # wait_quiet(quiet_seconds=0.40, timeout=4.0)

                ### CONFIRMED: self._log(f"***DEBUG[delete_one-1811] cat={cat}, msg_id={msg_id}, complete_prompt={bbs.read_complete_prompt}")
                self._adapter.wait_quiet(quiet_seconds=0.40, timeout=4.0)
                if self._adapter:
                    self._adapter.drain_buffer()
                self._log(f"Deleting {cat} message #{msg_id}: K {msg_id}")
                self._send_and_wait(f"K {msg_id}", bbs.read_complete_prompt)

            except Exception as e:
                self._log(f"WARNING: delete failed for message #{msg_id}: {e}")

                # Attempt a small resync so we don't poison the next delete.
                try:
                    self._adapter.wait_quiet(quiet_seconds=0.50, timeout=4.0)
                    if self._adapter:
                        self._adapter.drain_buffer()
                except Exception:
                    pass


        def _run_jnos_custom_bulletin_script() -> None:
            """ 260207
            JNOS Custom Bulletin Retrieval (mailbox-scoped):

              A <area>
              <list cmd>   (LA, L>, etc.)
              -> Read messages found in that listing BEFORE moving to next area

            Script source: bbs.retrieve_custom
            """
            if self.trace: 
                self._log(f">>>>>TRACE -- SendReceiveSession._run_jnos_custom_bulletin_script")

            script_text = str(getattr(bbs, "retrieve_custom", "") or "").strip()
            if not script_text:
                self._log("BULLETIN custom retrieval selected but retrieve_custom is empty; skipping")
                return

            parse_rows = getattr(bbs, "parse_message_listing_rows", None)
            if not callable(parse_rows):
                self._log("ERROR: JNOS custom bulletin retrieval requires parse_message_listing_rows()")
                return

            # Bulletin option: skip bulletins I sent
            try:
                skip_my_buls = bool(int(getattr(bbs, "skip_my_bulletins", 0) or 0))
            except Exception:
                skip_my_buls = bool(getattr(bbs, "skip_my_bulletins", False))

            current_area_hint = ""
            # Small local dict: msgno -> LM row (per listing block)
            # (We keep it per block because msg numbers are mailbox-local.)
            for raw in script_text.splitlines():
                line = (raw or "").strip()
                if not line:
                    continue
                if line.startswith("#") or line.startswith(";"):
                    continue

                up = line.upper()

                # ----------------------------
                # Area change: A <area>
                # ----------------------------
                if up.startswith("A "):
                    parts = line.split(None, 1)
                    area = parts[1].strip() if len(parts) == 2 else ""
                    current_area_hint = area.upper() if area else ""

                    if self._stop_requested():          # 260226  If aborted, then exit
                        return

                    self._adapter.wait_quiet(quiet_seconds=0.50, timeout=6.0)
                    self._adapter.drain_buffer()

                    self._log(f"Selecting mailbox/area ({line})")
                    self._send_and_wait(line, bbs.list_complete_prompt)

                    # drain any banner / counts
                    self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
                    self._adapter.drain_buffer()
                    continue

                # ----------------------------
                # Listing command: LA, L>, LB, etc.
                # (In custom mode, user controls selection; no TO filtering.)
                # After listing, READ NOW while still in this mailbox.
                # ----------------------------
                list_cmd = line

                if self._stop_requested():          # 260226  If aborted, then exit
                    return

                self._adapter.wait_quiet(quiet_seconds=0.50, timeout=6.0)
                self._adapter.drain_buffer()

                self._log(f"Retrieving BULLETIN message list ({list_cmd})")
                self._send_and_wait(list_cmd, bbs.list_complete_prompt)

                listing = self._adapter.drain_buffer() or ""
                if not listing.strip():
                    self._log(f"WARNING: BULLETIN listing buffer is empty for ({list_cmd})")
                    continue

                rows = parse_rows(listing) or []

                # 260207
                ### self._log(f"***DEBUG[SRS-2475]: listing_len={len(listing)} tail={listing[-200:].replace(chr(13),'')}")
                rows = parse_rows(listing) or []
                ### self._log(f"***DEBUG[SRS-2477]: parsed_rows={len(rows)} first_row={rows[0] if rows else None}")


                # Build ids in-order, de-duped, and map rows for JNOS fingerprint
                # listing_row_by_id={'1': {'new': 'Y', 'msgno': '1', 'to': 'cup@xsc', 'from': 'kn6pe', 'month': 'Mar', 'day': '3', 'size': '606', 'subject': 'OutpostX Dedupe Test #1', 'area_hint': 'ALLXSC'}}
                listing_row_by_id: dict[str, dict] = {}
                ids: list[str] = []

                for r0 in rows:
                    msgno = str((r0.get("msgno") or "")).strip()
                    if not msgno:
                        continue

                    # stamp area_hint for JNOS dedupe stability
                    r = dict(r0)
                    if current_area_hint:
                        r["area_hint"] = current_area_hint

                    # Skip my own bulletins if configured
                    if skip_my_buls:
                        from_field = str((r.get("from") or "")).strip()
                        if my_calls and any(from_field.upper() == c.upper() for c in my_calls):
                            continue

                    if msgno not in listing_row_by_id:
                        listing_row_by_id[msgno] = r
                        ids.append(msgno)

                self._log(f"BULLETIN eligible in area {current_area_hint or '(unknown)'}: {len(ids)} message(s)")

                # DEBUG ONLY (4 lines)
                if ids:
                    r0 = listing_row_by_id.get(ids[0], {})
                    ### CONFIRMED: self._log(f"***DEBUG[SRS-1917] LMROW keys={sorted(r0.keys())}")
                    ### CONFIRMED: self._log(f"***DEBUG[SRS-1918] LMROW sample={r0}")

                # **CRITICAL**: Read messages immediately, while still in this mailbox
                ### CONFIRMED: self._log(f"***DEBUG[SRS-1921] ids={ids}")
                ### CONFIRMED: self._log(f"***DEBUG[SRS-1922] listing_row_by_id={listing_row_by_id}")
                for mid in ids:
                    if getattr(self, "_stop_requested", None) and self._stop_requested():
                        self._log("Send/Receive: cancel requested (stopping JNOS custom script)")
                        return
                    _retrieve_one_message("BULLETIN", mid, listing_row_by_id)


        # ------------------------------------------------------------
        # BEGIN-------------------------------------------------------
        # ------------------------------------------------------------
        # Run list passes in order, retrieve messages in each pass
        # ------------------------------------------------------------
        # print("***DEBUG: bbs attrs =\n" + pformat(vars(bbs), width=120))
        for category in enabled:
            cat = (category or "").strip().upper()

            ### CONFIRMED: self._log(f">>>>> READY: List: cat={cat}, spec_id={spec_id}")
            # 260207
            # JNOS + BULLETIN + CUSTOM is mailbox-scoped: list and read must be coupled per area
            if cat == "BULLETIN" and spec_id == "jnos":
                mode = str(getattr(bbs, "retrieve_bulletins_mode", "") or "").strip().upper()
                if mode == "CUSTOM":
                    _run_jnos_custom_bulletin_script()
                    continue

            # For JNOS dedupe: keep LM rows by msg number for this pass
            listing_row_by_id: dict[str, dict] = {}

            # -------
            # RUN THE LIST COMMAND.  
            # For this category, return a list of message IDs
            # -------
            norm_ids = _list_ids_for_category(cat)
            ### self._log(f"**** DEBUG[2469]: norm_ids={norm_ids}")
            if not norm_ids:
                continue

            # ------------------------------------------------------------
            # Step through each Msg_id.  
            #
            # Retrieve, then Delete each message 
            # interleaving "K <id>" output with subsequent "R <id>" output.
            # ------------------------------------------------------------

            # get the 'delete_enabled' flag for 'PRIVATE' messages
            delete_enabled = bool(getattr(bbs, "delete_on_bbs", False))
            for msg_id in norm_ids:
                if getattr(self, "_stop_requested", None) and self._stop_requested():
                    self._log("Send/Receive: cancel requested (stopping inbound loop)")
                    return

                ### CONFIRMED: self._log(f"***DEBUG[-2011]: Retrieving '{cat}' msg '{msg_id}'")
                _retrieve_one_message(cat, msg_id, listing_row_by_id)

                ### CONFIRMED: self._log(f"***DEBUG[-2014]: DELETING '{cat}' msg '{msg_id}'")
                if  cat == "PRIVATE" and delete_enabled:
                    _delete_one_message(cat, msg_id)

        ### self._log(f"***DEBUG:SOUND received_new_count={received_new_count}")
        if received_new_count:
            self._log(f"Received {received_new_count} new message(s)")
            self._notify_messages_received(snap, received_new_count)

        # ------------------------------------------------------------
        # END ------------------------------------------------------------
        # ------------------------------------------------------------


    def _bbs_prompt_regex_and_flags(self, snap, fallback_prompt: str) -> tuple[str, bool]:
        """Return (prompt_regex_pattern, case_insensitive).

        - If a BBS spec is bound and includes prompt.pattern, treat it as a REGEX.
        - Otherwise treat fallback_prompt as a literal prompt string and escape it.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._bbs_prompt_regex_and_flags")

        bbs = getattr(snap, "bbs", None)
        spec = getattr(bbs, "spec", None) if bbs is not None else None
        if spec is not None:
            try:
                prompt = spec.raw.get("prompt", {}) or {}
                pat = (prompt.get("pattern") or "").strip()
                ci = bool(prompt.get("case_insensitive", True))
                if pat:
                    return pat, ci
            except Exception:
                pass

        # No spec-bound prompt → treat as literal
        lit = (fallback_prompt or ">").strip() or ">"
        return re.escape(lit), True


    # ------------------------------------------------------------------
    # Utility helper
    # ------------------------------------------------------------------
    def _normalize_email_address(self, value: str) -> str:
        """
        Normalize email-style addresses seen on packet BBSes.

        Examples:
        '<OBERMAIL@ATT.NET>' -> 'OBERMAIL@ATT.NET'
        'KN6PE@W1XSC.SCC-ARES-RACES.ORG' -> unchanged
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._normalize_email_address")

        if not value:
            return ""

        v = value.strip()
        if v.startswith("<") and v.endswith(">"):
            v = v[1:-1].strip()

        return v

    def _strip_trailing_prompt(
        self,
        text: str,
        prompt_pattern: str | None = None,
        *,
        case_insensitive: bool = False,
    ) -> str:
        """
        Remove the *trailing* BBS prompt line from captured text.

        We remove the line containing the *last* prompt match (and anything after it).
        This is safer than removing the first matching line, and avoids accidentally
        deleting message content if a prompt-like substring appears earlier.

        Important:
        Normalize CRLF / CR-only text first so line-boundary logic works for
        TELNET/WL2K responses that may end with '\\r\\rCMS>\\r'.
        """
        self._log(f">>>>>TRACE -- SendReceiveSession._strip_trailing_prompt")

        if not text:
            return text

        # Normalize all line endings to LF for consistent prompt stripping.
        s = text.replace("\r\n", "\n").replace("\r", "\n")

        pat = (prompt_pattern or "").strip()
        if not pat:
            return s.rstrip()

        flags = re.MULTILINE
        if case_insensitive:
            flags |= re.IGNORECASE

        # Compile as regex; if invalid, treat as literal
        try:
            rx = re.compile(pat, flags)
        except re.error:
            rx = re.compile(re.escape(pat), flags)

        # Find the last match anywhere in the text
        last = None
        for m in rx.finditer(s):
            last = m

        if not last:
            return s.rstrip()

        # Remove from the start of the line containing the last match
        cut_at = s.rfind("\n", 0, last.start())
        if cut_at == -1:
            # match is on the first line
            return ""

        return s[:cut_at].rstrip()

    # ------------------------------------------------------------------
    # Logout / Teardown
    # ------------------------------------------------------------------
    def _logout(self, snap: SessionSnapshot) -> None:
        """
        Best-effort session logout/teardown.

        Dispatch by interface type so each transport can perform the
        correct BBS logout and connection teardown sequence.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._logout")

        if self._stop_requested():  # 260226 JFIX
            raise SessionAbortRequested("Operator aborted session")

        if not self._adapter:
            return

        bbs = getattr(snap, "bbs", None)
        iface = getattr(snap, "interface", None)
        iface_data = getattr(iface, "data", {}) or {}
        if not isinstance(iface_data, dict):
            iface_data = {}
        iface_type = (str(iface_data.get("interface_type", "")) or "").strip().upper()

        # ------------------------------------------------------------
        # COMMON: Send the BBS init commands (AFTER): run after last BBS ops, before 'B' bye (260129)
        # ------------------------------------------------------------
        try:
            use_init = bool(getattr(bbs, "use_init_cmd", False))
        except Exception:
            use_init = False

        if use_init:
            raw = (getattr(bbs, "cmd_after", "") or "")
            for line in raw.splitlines():
                # allow ';' on a line to separate multiple commands
                for part in [p.strip() for p in line.split(";") if p.strip()]:
                    if self._stop_requested():
                        self._log("Send/Receive: cancel requested during BBS init(after)")
                        return

                    self._log(f"BBS init(after): {part}")
                    self._send_and_wait(part, bbs.command_prompt)
        else:
            self._log("BBS init(after): skipped (use_init_cmd is False)")


        # ------------------------------------------------------------
        # If Tactical Call, send Station ID
        # ------------------------------------------------------------
        self._send_tactical_station_id_if_needed(snap)

        # ------------------------------------------------------------
        # Redirect ot the appropriate IF type to finish up the closeout
        # ------------------------------------------------------------

        ### CONFIRMED.  self._log(f">>>>> iface_type={iface_type}")
        if iface_type in ("TNC_TAPR", "TNC_SCS"):
            self._logout_bbs_via_tnc(snap)
            return

        if iface_type == "TELNET":
            self._logout_bbs_via_telnet(snap)
            return

        if iface_type == "AGWPE":
            self._logout_bbs_via_agwpe(snap)
            return

        self._log(f"WARNING: unknown iface_type={iface_type!r}; using generic logout")
        self._logout_bbs_generic(snap)


    def _logout_bbs_via_tnc(self, snap: SessionSnapshot) -> None:
        """ 260114
        Attempt a polite BBS logout (best-effort), then wait for the TNC to confirm
        the RF disconnect before closing the COM port.

        Why: On congested RF, 'B' may take time to reach the BBS and/or the disconnect
        handshake may complete later. If we close the COM port too quickly, we never
        observe the TNC's '*** DISCONNECTED' confirmation and can leave the link in
        an uncertain state.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._logout_bbs_via_tnc")

        if not self._adapter:
            return

        iface = getattr(snap, "interface", None)
        iface_data = getattr(iface, "data", {}) or {}
        if not isinstance(iface_data, dict):
            iface_data = {}

        # ------------------------------------------------------------
        # 2) Send BBS "Bye"
        # ------------------------------------------------------------
        # Get the prompts from the Interface profile snapshot
        tnc_disconnect = (iface_data.get("tnc_disconnect_prompt") or "").strip()
        tnc_cmd_prompt = (iface_data.get("tnc_cmd_prompt") or "cmd:").strip()
        tnc_timeout    = (iface_data.get("tnc_timeout_prompt") or "").strip()

        try:
            # bbs = getattr(snap, "bbs", None)
            # bye = (getattr(bbs, "cmd_bye", None))
            bye = self._get_bye_command(snap)   # default "B"

            # If you later spec-drive this, you could do:
            # bye = (getattr(bbs, "spec", None) and bbs.spec.raw.get("commands", {}).get("bye")) or "B"
            self._log(f"Logging out: sending '{bye}' to BBS")
            self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
            self._adapter.drain_buffer()
            self._adapter.send_line(bye)
        except Exception:
            return

        # 2) Wait for TNC to report DISCONNECTED (then cmd:)
        # Use configured literal prompts when present; also include robust fallbacks.
        pats: list[str] = []
        if tnc_disconnect:
            pats.append(re.escape(tnc_disconnect))
        if tnc_timeout:
            pats.append(re.escape(tnc_timeout))

        # Robust fallbacks (covers common Kantronics/SCS variants)
        pats.extend([
            r"\*\*\*\s*DISCONNECTED",
            r"\*\*\*.*disconn",
        ])

        # Poll loop: don't hard-fail the whole session if logout confirm isn't seen,
        # but do make a best effort before closing the port.
        self._log("Waiting for TNC disconnect confirmation...")
        start = time.time()
        hard_timeout = 60.0  # conservative; RF disconnect can take time

        saw_disconnect = False
        last_log = 0.0

        while time.time() - start < hard_timeout:
            if self._stop_requested():
                break

            now = time.time()
            if now - last_log > 15.0:
                self._log("...still waiting for TNC 'DISCONNECTED' (RF may be slow)")
                last_log = now

            try:
                matched = self._adapter.expect_any_match(pats, timeout=1.0)
            except TimeoutError:
                continue

            # If we matched a timeout/failure token, stop waiting
            if tnc_timeout and matched == re.escape(tnc_timeout):
                self._log("WARNING: TNC timeout observed during logout wait")
                break

            # Otherwise treat as disconnect confirmation
            saw_disconnect = True
            break

        if saw_disconnect:
            self._log("TNC disconnect confirmed. Waiting for cmd prompt...")
            try:
                # After DISCONNECTED, most TNCs return to cmd: prompt shortly after.
                self._adapter.expect(re.escape(tnc_cmd_prompt), timeout=5.0)
            except Exception:
                # Not fatal; we at least saw the disconnect indication.
                pass

            # ------------------------------------------------------------
            # Post-session TNC init commands (tnc_init_after)
            # ------------------------------------------------------------
            send_init = bool(iface_data.get("tnc_send_init_cmds", True))

            if not send_init:
                self._log("TNC init(after): skipped (tnc_send_init_cmds is False)")

            else:
                raw_init = iface_data.get("tnc_init_after", []) or []

                if isinstance(raw_init, str):
                    init_cmds = raw_init.splitlines()
                else:
                    init_cmds =list(raw_init)

                # self._log(f"***DEBUG: tnc_init_after={init_cmds}")
                for cmd in init_cmds:
                    if self._stop_requested():
                        self._log("Send/Receive: cancel requested during TNC init(after)")
                        return

                    cmd = str(cmd).rstrip("\r\n")
                    if not cmd:
                        continue

                    if self._stop_requested():          # 260226  If aborted, then exit
                        return

                    self._log(f"TNC init(after): {cmd}")
                    self._send_to_tnc_and_wait_prompt(cmd, tnc_cmd_prompt, timeout=2.0)
        else:
            self._log("WARNING: Did not observe TNC disconnect confirmation before close")

        # Drain any tail so next session starts clean
        try:
            self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
        except Exception:
            pass
        try:
            self._adapter.drain_buffer()
        except Exception:
            pass


    def _logout_bbs_via_telnet(self, snap: SessionSnapshot) -> None:
        """
        Best-effort TELNET logout.

        Goal:
        1) get and send BBS bye command
        2) allow remote side a moment to respond/close
        3) drain any tail text for transcript/logging
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._logout_bbs_via_telnet")

        if not self._adapter:
            return

        bye = self._get_bye_command(snap)   # default "B"
        ### CONFIRED: self._log(f">>>>> bye='{bye}'")
        try:
            self._log(f"Logging out via TELNET: sending {bye!r}")
            self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
        except Exception:
            pass

        try:
            self._adapter.drain_buffer()
            self._adapter.send_line(bye)
        except Exception as e:
            self._log(f"WARNING: TELNET logout send failed: {e}")
            return

        # Best-effort tail capture only; no TNC disconnect semantics here.
        try:
            self._adapter.wait_quiet(quiet_seconds=0.50, timeout=3.0)
        except Exception:
            pass

        try:
            tail = self._adapter.drain_buffer() or ""
            if tail.strip():
                self._log_rx_text(tail)
        except Exception:
            pass     


    def _logout_bbs_via_agwpe(self, snap: SessionSnapshot) -> None:
        """
        AGWPE logout:
        1) send BBS bye command if we are still connected
        2) accept either BBS prompt or AGWPE disconnect as success
        3) unregister our callsign
        4) socket close happens later in _close_connection()

        Note: 
        This changes how OutpostX interprets the end of an AGWPE session.
          * stopped using the generic helper for AGWPE bye
          * The outcome list now includes disconnect as success
              both 'BBS prompt' and '*** DISCONNECTED...' are acceptable exit paths
          * The warning path is narrower such as 'timeout', 'unexpected response', 'some true error'
              and no longer  warns on a normal disconnect.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._logout_bbs_via_agwpe")

        if not self._conn or not self._adapter:
            return

        conn = self._conn
        bbs = getattr(snap, "bbs", None)
        bye = self._get_bye_command(snap) or "B"

        if getattr(conn, "is_bbs_connected", False):
            try:
                done_prompt = (getattr(bbs, "command_prompt", None) or ">").strip()
                bbs_pat, _ci = self._get_bbs_prompt_pattern(snap, fallback_prompt=done_prompt)

                pats = [
                    bbs_pat,
                    r"\*\*\*\s*DISCONNECTED.*",
                    r"\*\*\*.*disconn",
                    r"RETRYOUT",
                ]

                self._log(f"Logging out via AGWPE: sending {bye!r}")
                self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
                self._adapter.drain_buffer()
                self._log(f"TX: {bye}")
                self._adapter.send_line(bye)

                end = time.time() + 15.0
                while time.time() < end:
                    if self._stop_requested():
                        break

                    try:
                        matched = self._adapter.expect_any_match(pats, timeout=1.0)
                    except TimeoutError:
                        continue

                    if matched == bbs_pat:
                        self._log("AGWPE: bye returned to BBS prompt")
                        break

                    if matched in (r"\*\*\*\s*DISCONNECTED.*", r"\*\*\*.*disconn"):
                        self._log("AGWPE: disconnect observed after bye")
                        break

                    tail = self._adapter.drain_buffer() or ""
                    self._log(
                        f"WARNING: unexpected AGWPE logout response matched={matched!r}. "
                        f"Last RX tail:\n{tail[-600:]}"
                    )
                    break

            except Exception as e:
                self._log(f"WARNING: AGWPE bye failed: {e}")

            try:
                if hasattr(conn, "wait_for_disconnect"):
                    conn.wait_for_disconnect(timeout=5.0)
            except Exception:
                pass

        try:
            if getattr(conn, "is_registered", False):
                self._log("AGWPE: unregistering callsign")
                conn.unregister()
        except Exception as e:
            self._log(f"WARNING: AGWPE unregister failed: {e}")


    def _get_bye_command(self, snap: SessionSnapshot) -> str:
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._get_bye_command")

        bbs = getattr(snap, "bbs", None)
        bye = getattr(bbs, "cmd_bye", None)
        return bye


    ###vvv+++
    def _run_path_script_if_needed(self, snap=None) -> None:
        """
        Run the configured path script before BBS login begins.

        First-pass integration rules
        ----------------------------
        - Enabled for TNC/serial and TELNET sessions.
        - Runs only when the selected BBS profile indicates SCRIPT mode
        and non-empty script text is present.
        - Uses the existing adapter so transcript/logging behavior remains
        consistent with normal Send/Receive operations.

        Expected profile fields
        -----------------------
        This first pass looks for the following BBS profile attributes:
        - path_type
        - path_script
        - path_timeout

        The exact field names may need to be adjusted to match the current
        profile/model names used in your code base.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._run_path_script_if_needed")

        bbs = getattr(snap, "bbs", None) if snap is not None else None
        iface = getattr(snap, "interface", None) if snap is not None else None

        # CONFIRMED: self._log(f">>>>>TRACE -- SendReceiveSession._run_path>iface={iface}")
        if bbs is None or iface is None:
            return

        iface_data = getattr(iface, "data", {}) or {}
        interface_type = (str(iface_data.get("interface_type", "")) or "").strip().upper()
        #### self._log(f">>>>>TRACE -- SendReceiveSession._run_path>interface_type={interface_type}")
        if interface_type not in ("TNC_TAPR", "TNC_SCS", "TELNET"):
            return

        path_type = (getattr(bbs, "path_type", "") or "").strip().upper()
        #### self._log(f">>>>>TRACE -- SendReceiveSession._run_path...path_type = {path_type}")
        if path_type != "NODE":
            return

        script_text = (getattr(bbs, "path_script", "") or "").strip()
        if not script_text:
            self._log("PathScript: SCRIPT mode selected, but no script text is defined")
            return

        default_timeout = getattr(bbs, "path_script_timeout", 10) or 10

        self._log("PathScript: invoking runner")

        ctx = PathScriptContext(
            adapter=self._adapter,
            log=self._log,
            is_stop_requested=lambda: self._stop_requested(),
        )

        runner = PathScriptRunner(ctx, default_timeout=float(default_timeout))

        try:
            runner.run(script_text)

        # This exception is raised when we already requested cancel (via stop_requested()).
        except PathScriptAbortedError:
            self._log("PathScript: aborted by operator")
            self._log("PathScript: aborting upstream connection")
            self.abort()
            raise
        
        except PathScriptError as exc:
            self._log(f"PathScript: failed - {exc}")
            self._log("PathScript: aborting upstream connection")
            self.abort()
            raise


    def _close_connection(self) -> None:
        """
        Close the underlying transport connection (best-effort cleanup).
        
        Always clears the adapter first so no further I/O is attempted during teardown.
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._close_connection")

        if not self._conn:
            return
        try:
            # Prefer explicit disconnect() if it exists and is callable
            disc = getattr(self._conn, "disconnect", None)
            if callable(disc):
                disc()
            else:
                # Some transports use close()
                close = getattr(self._conn, "close", None)
                if callable(close):
                    close()
        except Exception as e:
            self._log(f"WARNING: disconnect failed: {e}")
        finally:
            self._conn = None
            self._adapter = None


    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------
    def _notify_messages_received(self, snap: SessionSnapshot, count: int) -> None:
        """
        Notify the operator that new inbound messages were received.

        First implementation:
        - honor play_sound_on_receive
        - log what would happen
        - actual audio playback can be wired in the UI/dialog layer next
        """
        sr = getattr(snap, "send_receive_settings", None)
        if not sr:
            return

        ### self._log(f"***DEBUG:SOUND: sr={sr}")

        if not bool(getattr(sr, "play_sound_on_receive", False)):
            return

        sound_path = (getattr(sr, "sound_file_path", "") or "").strip()

        self._messages_received({
            "count": count,
            "play_sound": True,
            "sound_path": sound_path,
        })

    # ------------------------------------------------------------------
    #  Various TAG Helpers
    # ------------------------------------------------------------------
    def _apply_outbound_wire_tags(self, msg, body_text: str) -> str:
        """
        Apply Outpost wire-format tags immediately before transmit.

        This does not modify the stored message body.
        """
        tags: list[str] = []

        self._log(f"****DEBUG, RECEIPTS, _apply_outbound_wire_tags, msg={msg}")

        if bool(getattr(msg, "is_rdr", False)):
            tags.append(WIRE_TAG_RDR)

        if bool(getattr(msg, "is_urgent", False)):
            tags.append(WIRE_TAG_URGENT)

        if bool(getattr(msg, "is_encoded", False)):
            tags.append(WIRE_TAG_BASE64)

        if not tags:
            return body_text or ""

        text = body_text or ""

        # Avoid double-tagging if a body already starts with one of our tags.
        stripped = text.lstrip()
        already_tagged = any(stripped.startswith(tag) for tag in WIRE_TAGS)
        if already_tagged:
            return text

        return "".join(tags) + "\n" + text


    def _strip_inbound_wire_tags(self, body_text: str) -> tuple[str, dict[str, bool]]:
        text = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")

        flags = {
            "is_rdr": False,
            "is_urgent": False,
            "is_encoded": False,
        }

        lines = text.split("\n")
        if not lines:
            return text, flags

        first = lines[0].strip()

        # Support stacked tags on first line, e.g. !RDR!!URG!
        changed = False
        while first:
            if first.startswith(WIRE_TAG_RDR):
                flags["is_rdr"] = True
                first = first[len(WIRE_TAG_RDR):].strip()
                changed = True
            elif first.startswith(WIRE_TAG_URGENT):
                flags["is_urgent"] = True
                first = first[len(WIRE_TAG_URGENT):].strip()
                changed = True
            elif first.startswith(WIRE_TAG_BASE64):
                flags["is_encoded"] = True
                first = first[len(WIRE_TAG_BASE64):].strip()
                changed = True
            else:
                break

        if not changed:
            return text, flags

        # If tag line contained only tags, remove the whole first line.
        # If it had extra text after tags, preserve that text as the new first line.
        if first:
            cleaned_lines = [first] + lines[1:]
        else:
            cleaned_lines = lines[1:]

        cleaned = "\n".join(cleaned_lines).lstrip("\n")
        return cleaned, flags


    # ------------------------------------------------------------------
    #  MID Helpers P132
    # ------------------------------------------------------------------
    def _active_msg_id_prefix(self, snap) -> str:
        tactical = getattr(snap, "tactical", None)
        station = getattr(snap, "station", None)

        tactical_prefix = (getattr(tactical, "msg_id_prefix", "") or "").strip().upper()
        station_prefix = (getattr(station, "msg_id_prefix", "") or "").strip().upper()

        return tactical_prefix or station_prefix


    # ------------------------------------------------------------------
    #  Delivery Receipt Helpers
    # ------------------------------------------------------------------
    def _should_send_delivery_receipt(
        self,
        *,
        category: str,
        from_call: str,
        subject: str,
        request_delivery_receipt: bool,
        snap,
    ) -> bool:
        """
        Decide whether OutpostX should automatically send a Delivery Receipt.

        OutpostX rules:
        - do not send for Bulletins
        - do not send if subject already contains DELIVERED
        - do not send to MAILER-DAEMON
        - do not send to MAILER@
        - always send for an incoming '!RDR! tag, or
        - always send when message setting 'Always send a delivery receipt' is checked
        """
        if self.trace:
            self._log(f">>>>>TRACE -- SendReceiveSession _should_send_delivery_receipt ")

        ms = getattr(snap, "message_settings", None)
        local_send_dr = bool(getattr(ms, "send_dr", False)) if ms else False

        requested_by_sender = bool(request_delivery_receipt)

        if not requested_by_sender and not local_send_dr:
            return False

        if (category or "").strip().upper() == "BULLETIN":
            return False

        subj = (subject or "").strip().upper()
        if "DELIVERED" in subj:
            return False

        frm = (from_call or "").strip().upper()
        if frm == "MAILER-DAEMON":
            return False
        if frm.startswith("MAILER@"):
            return False

        return True



    def _send_one_delivery_receipt(
        self,
        *,
        to_call: str,
        delivered_to: str,
        original_subject: str,
        assigned_msg_id: str,
        add_local_mid: bool,
        snap,
    ) -> None:
        """
        Immediately send one Delivery Receipt during the current BBS session.

        This does not create an outbound DB message. It behaves like a protocol
        acknowledgment sent during the active receive session.
        """
        self._log(f"***DEBUG RECEIPT: in _send_one_delivery_receipt ")
        if self._stop_requested():
            return

        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")

        to_call = (to_call or "").strip()
        delivered_to = (delivered_to or "").strip()
        original_subject = (original_subject or "").strip()
        assigned_msg_id = (assigned_msg_id or "").strip()

        original_subject = (original_subject or "").strip()
        self._log(f"***DEBUG RECEIPT: to_call={to_call}, delivered_to={delivered_to}, original_subject={original_subject}, assigned_msg_id={assigned_msg_id} ")

        if not to_call:
            self._log("WARNING: Delivery Receipt skipped; original sender is blank")
            return

        bbs = snap.bbs

        subject = f"DELIVERED: {original_subject}" if original_subject else "DELIVERED:"
        now_txt = datetime.now().strftime("%m/%d/%Y %H:%M")

        body_lines = [
            "Your message was delivered to:",
            f"{delivered_to} at {now_txt}",
        ]

        if add_local_mid:
            body_lines.append(f"{delivered_to} assigned Msg ID: {assigned_msg_id}")

        eom = (getattr(bbs, "end_of_message", None) or "/EX").strip()
        done_prompt = (getattr(bbs, "command_prompt", None) or ">").strip()

        send_cmd = f"SP {to_call}"

        self._log(f"Sending Delivery Receipt to {to_call}")
        self._log(f"TX: {send_cmd}")
        self._log(f"TX: {subject}")
        self._log(f"TX: <{len(body_lines)} receipt body line(s)>")
        self._log(f"TX: {eom}")

        tx_lines = [send_cmd, subject]
        tx_lines.extend(body_lines)
        tx_lines.append(eom)

        for line in tx_lines:
            if self._stop_requested():
                self._log("Send/Receive: cancel requested while sending Delivery Receipt")
                return
            self._adapter.send_line(line)

        self._wait_for_prompt_or_abort(done_prompt=done_prompt, snap=snap, poll_timeout=1.0)
        self._adapter.drain_buffer()

    # ------------------------------------------------------------------
    #  ## PRINT Helpers
    # ------------------------------------------------------------------

    def _auto_print_received_message(
        self,
        *,
        snap: SessionSnapshot,
        msgidx: int,
        bbs_call: str,
        from_call: str,
        to_call: str,
        subject: str,
        sent_at_normalized: str | None,
        body_text: str,
    ) -> None:
        """
        Auto-print one newly received message immediately after it is stored.

        This is intentionally per-message, not batch-oriented, so a long receive
        session does not delay delivery of earlier traffic to the served agency.
        """
        sr = getattr(snap, "send_receive_settings", None)
        if not sr or not bool(getattr(sr, "print_received", False)):
            return

        copies = max(1, min(int(getattr(sr, "print_received_copies", 1) or 1), 9))
        include_headers = bool(getattr(sr, "print_plain_headers", True))

        # Creat ethe message for printing directly from the DB
        printable = self._build_printable_message_from_repo(msgidx)
        if not printable:
            return

        try:
            MessagePrintService().print_message_silent(
                printable,
                include_headers=include_headers,
                copies=copies,
            )
            self._log(
                f"Auto-Print: queued received message for printing, msgidx={msgidx} "
                f"({copies} cop{'y' if copies == 1 else 'ies'})"
            )
        except Exception as exc:
            self._log(f"WARNING: Auto-Print failed for received message msgidx={msgidx}: {exc}")


    def _auto_print_sent_message(
        self,
        *,
        snap: SessionSnapshot,
        msgidx: int,
    ) -> None:
        """
        Auto-print one outbound message immediately after it is marked SENT.

        This mirrors received-message Auto-Print, but uses the sent-message
        settings and copy count.
        """
        sr = getattr(snap, "send_receive_settings", None)
        if not sr or not bool(getattr(sr, "print_sent", False)):
            return

        copies = max(1, min(int(getattr(sr, "print_sent_copies", 1) or 1), 9))
        include_headers = bool(getattr(sr, "print_plain_headers", True))

        printable = self._build_printable_message_from_repo(msgidx)
        if not printable:
            self._log(f"WARNING: Auto-Print could not build sent printable message msgidx={msgidx}")
            return

        try:
            MessagePrintService().print_message_silent(
                printable,
                include_headers=include_headers,
                copies=copies,
            )
            self._log(
                f"Auto-Print: queued sent message for printing; msgidx={msgidx} "
                f"({copies} cop{'y' if copies == 1 else 'ies'})"
            )
        except Exception as exc:
            self._log(f"WARNING: Auto-Print failed for sent message msgidx={msgidx}: {exc}")


    def _build_printable_message_from_repo(self, msgidx: int) -> PrintableMessage | None:
        """
        Build a PrintableMessage from repository data.

        This ensures printing always reflects the stored message,
        not transient parsed values.
        """
        if not self._message_repo:
            return None

        got = self._message_repo.get(msgidx)
        if not got:
            return None

        msg, body = got

        body_text = ""
        if body and getattr(body, "message", None):
            body_text = body.message or ""

        return PrintableMessage(
            title_call=(msg.bbs_call or "OutpostX").strip(),
            from_call=msg.from_call or "",
            to_call=msg.to_call or "",
            sent_at=msg.sent_at or "",
            subject=msg.subject or "",
            local_msg_id=str(msgidx),
            body=body_text,
        )


    def _resolve_session_mycall(self, snap: SessionSnapshot) -> str:
        """
        Return the callsign to use for this session's on-air identity.

        Tactical Call rule:
        - legal_call_sign is always required
        - tactical_call_sign, when active/present, overrides legal_call_sign
            for MYCALL / connection identity
        """
        station = getattr(snap, "station", None)
        tactical = getattr(snap, "tactical", None)

        legal_call = (getattr(station, "legal_call_sign", "") or "").strip().upper()
        tactical_call = (getattr(tactical, "tactical_call_sign", "") or "").strip().upper()

        if not legal_call:
            raise RuntimeError(
                "Send/Receive: Active station legal call is empty. "
                "Cannot set MYCALL and cannot continue session safely."
            )

        return tactical_call or legal_call


    def _send_tactical_station_id_if_needed(self, snap: SessionSnapshot) -> None:
        """
        If an active Tactical ID is configured, send the FCC/operator station ID
        line before leaving the BBS.

        Format:
            # this is <legal_call_sign>, <tactical_location>
        """
        if not self._adapter:
            return

        station = getattr(snap, "station", None)
        tactical = getattr(snap, "tactical", None)

        legal_call = (getattr(station, "legal_call_sign", "") or "").strip().upper()
        tactical_call = (getattr(tactical, "tactical_call_sign", "") or "").strip().upper()
        tactical_location = (getattr(tactical, "tactical_location", "") or "").strip()

        if not tactical_call:
            return

        if not legal_call:
            raise RuntimeError(
                "Send/Receive: Active station legal call is empty. "
                "Cannot send Tactical Station ID."
            )

        if tactical_location:
            station_id = f"# this is {legal_call} as {tactical_call}, {tactical_location}"
        else:
            station_id = f"# this is {legal_call} as {tactical_call}"

        self._log(f"Tactical station ID: {station_id}")
        self._adapter.send_line(station_id)

        try:
            self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)
        except Exception:
            pass


    def _send_and_wait(self, command: str, done_prompt: str, timeout: float = 20.0) -> None:
        """
        Send a command and wait until a completion prompt is observed.

        This helper is designed for **BBS / RF-oriented command flows**, where
        output may arrive slowly, in bursts, or interleaved with unrelated text.

        Behavior:
            - Drains any stale buffer content before sending the command to avoid
            matching previously-seen prompts.
            - Sends the command via the transport.
            - Waits (defensively) for one of the expected completion prompts,
            accounting for RF latency, partial output, and retry noise.

        Why this exists:
            - BBS interactions occur over RF or other high-latency links.
            - Prompts may be delayed, repeated, or preceded by banner text.
            - Conservative buffer discipline is required to avoid
            desynchronizing the session.

        Safe to use:
            - BBS commands (LM, R, SP, SB, etc.)
            - Any command where responses may arrive over RF
            - Any flow that expects BBS banners or menus
            (e.g. 'ENTER COMMAND:')

        Do NOT use:
            - Local TNC command mode
            - TNC init-before or init-after commands
            - Any situation where you are synchronizing on the literal
            TNC 'cmd:' prompt

        For local TNC command flows, use:
            _send_to_tnc_and_wait_prompt()
        """
        # if self.trace: 
        #     self._log(f">>>>>TRACE -- SendReceiveSession._send_and_wait")

        if not self._adapter:
            raise RuntimeError("adapter not initialized")

        # Let any trailing bytes from the previous prompt finish arriving
        self._adapter.wait_quiet(quiet_seconds=0.20, timeout=2.0)

        # CRITICAL: remove any prior prompt/echo/garbage so expect() can't match “old” data
        self._adapter.drain_buffer()

        self._log(f"TX: {command}")
        self._adapter.send_line(command)

        # Give the last chunk a moment to land (optional but helps at 1200 baud)
        self._wait_for_prompt_or_abort(done_prompt=done_prompt, snap=self.snap, poll_timeout=1.0)

        # ------------------------------------------------------------------
        # Adapter Buffer Discipline (RF-safe command boundary)
        #
        # On RF links (1200 baud / small packet sizes), output arrives in bursts and
        # the *tail* of a prior prompt/banner can show up late. If we don’t pre-drain,
        # expect() can accidentally match “old” prompt text still sitting in the buffer.
        #
        # Rule:
        #   Always do: wait_quiet() -> drain_buffer() -> send command -> wait for prompt
        #
        # This prevents:
        #   - matching a stale prompt from the previous command
        #   - LM output being contaminated by the tail of a prior command
        #   - R # reads terminating early due to an earlier prompt match
        #
        # Buffer Discipline summary:
        #   1) quiet  -> let trailing bytes finish arriving
        #   2) drain  -> remove stale prompt/echo so matching can’t hit old text
        #   3) expect -> match the completion prompt/failure patterns only from new RX
        #
        # Applies to: _send_and_wait() and _wait_for_prompt_or_abort()
        # ------------------------------------------------------------------
    def _wait_for_prompt_or_abort(self, *, done_prompt: str, snap, poll_timeout: float = 1.0) -> None:
        """
        Wait for an expected completion prompt, or abort early if a terminal
        error condition is detected.

        Behavior:
            - Waits for the BBS completion prompt.
            - Also watches for known failure patterns.
            - If the operator presses Cancel, actively issues abort/disconnect
              and raises SessionAbortRequested so the session unwinds immediately.
            - keep this function as the single owner of abort during waits
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._wait_for_prompt_or_abort")

        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")

        bbs = snap.bbs
        iface = snap.interface

        # Success prompt (BBS command prompt)
        bbs_prompt = (done_prompt or getattr(bbs, "command_prompt", None) or ">").strip()
        bbs_pat, _prompt_ci = self._get_bbs_prompt_pattern(snap, fallback_prompt=bbs_prompt)

        # Failure prompts (from InterfaceProfile.data)
        iface_data = getattr(iface, "data", {}) or {}
        if not isinstance(iface_data, dict):
            iface_data = {}

        tnc_disconnect = (iface_data.get("tnc_disconnect_prompt") or "").strip()
        tnc_timeout = (iface_data.get("tnc_timeout_prompt") or "").strip()

        fail_pats: list[str] = []
        if tnc_disconnect:
            fail_pats.append(re.escape(tnc_disconnect))
        if tnc_timeout:
            fail_pats.append(re.escape(tnc_timeout))

        # Robust fallbacks
        fail_pats.extend([
            r"\*\*\*.*retry count exceeded",
            r"\*\*\*.*disconn",
        ])

        patterns = [bbs_pat] + fail_pats

        last_log = 0.0
        while True:
            if self._stop_requested():
                self._log("Send/Receive: cancel requested; issuing abort/disconnect")
                self.abort()
                raise SessionAbortRequested("Operator aborted session")

            now = time.time()
            if now - last_log > 30.0:
                self._log(f"Waiting for BBS prompt '{bbs_prompt}' (RF may be slow)...")
                last_log = now

            try:
                matched = self._adapter.expect_any_match(patterns, timeout=poll_timeout)
            except TimeoutError:
                continue  # not fatal; keep polling

            if matched == bbs_pat:
                return  # success

            # Failure pattern matched
            tail = ""
            try:
                tail = self._adapter.drain_buffer() or ""
            except Exception:
                pass

            raise RuntimeError(
                f"Command failed before BBS prompt. matched={matched!r}. "
                f"Last RX tail:\n{tail[-600:]}"
            )


    def _send_to_tnc_and_wait_prompt(self, command: str, tnc_prompt: str, timeout: float = 2.0) -> None:
        """
        Send a single command to a local TNC and wait for the literal TNC prompt.

        This helper is intentionally narrow in scope and should only be used
        when the session is in **TNC command mode**.

        Behavior:
            1) Sends the command verbatim to the TNC.
            2) Waits for the literal TNC command prompt (e.g. 'cmd:').
            3) Optionally drains any residual output so the next command
            starts from a clean prompt.

        Why this exists (do NOT replace with _send_and_wait):
            - Communication is local (computer ↔ TNC), not over RF.
            - There is no RF latency or framing uncertainty.
            - We are synchronizing on the TNC 'cmd:' prompt, not a BBS banner
            or 'ENTER COMMAND:' menu.
            - The RF-oriented buffer discipline in _send_and_wait()
            (pre-drain, quiet waits, abort patterns) can desynchronize fast
            local TNC command flows.

        Safe to use:
            - Before BBS connect (TNC init commands)
            - After BBS disconnect, once the TNC has returned to 'cmd:'

        Do NOT use:
            - After issuing a BBS connect command
            - For any command that expects BBS prompts or RF responses
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._send_to_tnc_and_wait_prompt")

        if not self._adapter:
            raise RuntimeError("adapter not initialized")

        self._log(f"TX: {command}")
        self._adapter.send_line(command)

        # For local TNC command mode, use a direct expect (no RF-safe pre-drain).
        self._adapter.expect(re.escape(tnc_prompt), timeout=timeout)

        # Optional: capture/clear the response so next command starts clean
        try:
            self._adapter.wait_quiet(quiet_seconds=0.05, timeout=0.5)
        except Exception:
            pass
        self._adapter.drain_buffer()


    def _get_bbs_prompt_pattern(
        self,
        snap,
        *,
        fallback_prompt: Optional[str] = None
    ) -> tuple[str, bool]:
        """
        Return (prompt_regex, case_insensitive) for detecting the BBS command prompt.

        Priority:
          1) Bound BBS spec prompt.pattern (treated as REGEX)
          2) fallback_prompt (treated as LITERAL)
          3) '>' as a final fallback
        """
        if self.trace: 
            self._log(f">>>>>TRACE -- SendReceiveSession._get_bbs_prompt_pattern")

        bbs = getattr(snap, "bbs", None)
        spec = getattr(bbs, "spec", None) if bbs else None

        if spec is not None:
            try:
                prompt_cfg = spec.raw.get("prompt", {}) or {}
                pat = (prompt_cfg.get("pattern") or "").strip()
                if pat:
                    ci = bool(prompt_cfg.get("case_insensitive", True))
                    return pat, ci
            except Exception:
                pass

        # Literal fallback
        lit = (
            fallback_prompt
            or getattr(bbs, "command_prompt", None)
            or ">"
        ).strip() or ">"

        return re.escape(lit), True


    def _wait_for_any_or_abort(
        self,
        *,
        patterns: list[str],
        success_pattern: str,
        timeout: float,
        context: str,
        poll_timeout: float = 1.0,
    ) -> str:
        """
        Poll for any of the supplied patterns while honoring Cancel/Abort.

        Returns:
            The exact matched pattern.

        Raises:
            SessionAbortRequested:
                If the operator presses Cancel.

            TimeoutError:
                If the overall timeout expires.

            RuntimeError:
                If a non-success pattern is matched.
        """
        if not self._adapter:
            raise RuntimeError("SendReceiveSession: adapter not initialized")

        end = time.time() + timeout
        last_log = 0.0

        while time.time() < end:
            if self._stop_requested():
                self._log("Send/Receive: cancel requested; issuing abort/disconnect")
                self.abort()
                raise SessionAbortRequested("Operator aborted session")

            now = time.time()
            if now - last_log > 30.0:   # refresh the log entry every 30 seconds
                self._log(f"Waiting: {context} (RF may be slow)...")
                last_log = now

            try:
                matched = self._adapter.expect_any_match(patterns, timeout=poll_timeout)
            except TimeoutError:
                continue

            if matched == success_pattern:
                return matched

            tail = self._adapter.drain_buffer() or ""
            raise RuntimeError(
                f"{context.capitalize()} failed before success pattern. "
                f"matched={matched!r}. Last RX tail:\n{tail[-600:]}"
            )

        tail = self._adapter.drain_buffer() or ""
        raise TimeoutError(
            f"Timeout {context}. Last RX tail:\n{tail[-600:]}"
        )


    # ------------------------------------------------------------------
    #  Date/Time Parser Helper (outside the class)
    # ------------------------------------------------------------------
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

def _derive_year_from_month_day(mon: int, day: int, *, now_utc: datetime) -> int:
    """
    Outpost year-derivation rule when year is absent:

      msg_md = (mon, day)
      today_md = (today_mon, today_day)   [UTC]
      if msg_md <= today_md: year = this year
      else: year = last year
    """
    msg_md = (mon, day)
    today_md = (now_utc.month, now_utc.day)
    return now_utc.year if msg_md <= today_md else (now_utc.year - 1)


def _parse_bbs_datetime_to_iso(
    value: str | None,
    *,
    default_year: int | None = None,
    assume_timezone: str = "utc",   # "utc" or "local"
    log=None,
) -> str | None:
    """
    Normalize a variety of BBS date/time strings into a consistent ISO string.

    Conventions:
      - If assume_timezone == "local": return local-naive ISO: "YYYY-MM-DDTHH:MM:SS"
      - Else (default "utc"): return UTC ISO with Z: "YYYY-MM-DDTHH:MM:SSZ"

    Supported inputs (examples):
      - ISO-ish: "2026-01-31T16:30:47", "...Z", "...-08:00"
      - RFC2822-ish: "Mon, 11 Apr 2011 19:58:02 PDT", "06 Jan 2014 02:43:51 +0000"
      - KPC3 list header: "01/21/07 10:01:43" or "01/21/2007 10:01:43"
      - BPQ: "22-Jan 22:46Z" or "22-Jan 22:46"
      - FBB: "10-Oct 23:31" (year inferred)
      - Some BBS short form: "0212/0945" (MMDD/HHMM, year inferred)

    Notes:
      - For missing years, default_year is used if provided; otherwise current year.
      - For date-only formats (no time), time is set to 00:00:00.
    """
    if not value:
        return None

    s = str(value).strip()
    if not s:
        return None

    tz_mode = (assume_timezone or "utc").strip().lower()
    if tz_mode not in ("utc", "local"):
        tz_mode = "utc"

    def _as_output(dt: datetime) -> str:
        """Format dt according to tz_mode."""
        if tz_mode == "local":
            # Store/display as local-naive clock time
            if dt.tzinfo is not None:
                dt = dt.astimezone()  # convert to local tz
            return dt.replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")

        # Store as UTC with Z
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---------------------------------------------------
    # 0) Already ISO? (KPC3 parse_full_message may emit this)
    # Accept: "YYYY-MM-DDTHH:MM:SS" or "...Z" or with offset.
    # ---------------------------------------------------
    try:
        iso = s
        if iso.endswith("Z"):
            dt = datetime.fromisoformat(iso[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(iso)
        return _as_output(dt)
    except Exception:
        pass

    # ---------------------------------------------------
    # 0a) RFC 2822 / email-style date (JNOS "Date:" header)
    # e.g. "Mon, 11 Apr 2011 19:58:02 PDT"
    #      "06 Jan 2014 02:43:51 +0000"
    # ---------------------------------------------------
    try:
        # Normalize common timezone abbreviations to numeric offsets for reliable parsing
        # (parsedate_to_datetime is not consistently reliable with PDT/PST across platforms)
        m_tz = re.search(r"\b([A-Za-z]{2,4})\s*$", s)
        tz_map = {
            "UTC": "+0000", "GMT": "+0000",
            "PST": "-0800", "PDT": "-0700",
            "MST": "-0700", "MDT": "-0600",
            "CST": "-0600", "CDT": "-0500",
            "EST": "-0500", "EDT": "-0400",
        }
        if m_tz:
            abbr = m_tz.group(1).upper()
            if abbr in tz_map:
                s_norm = re.sub(rf"\b{abbr}\s*$", tz_map[abbr], s)
            else:
                s_norm = s
        else:
            s_norm = s

        dt = parsedate_to_datetime(s_norm)
        return _as_output(dt)
    except Exception:
        pass

    # ---------------------------------------------------
    # 0b) MM/DD/YYYY HH:MM:SS or MM/DD/YY HH:MM:SS  (KPC3 listing)
    # ---------------------------------------------------
    try:
        dt = datetime.strptime(s, "%m/%d/%Y %H:%M:%S")
        return _as_output(dt)
    except Exception:
        pass

    try:
        dt = datetime.strptime(s, "%m/%d/%y %H:%M:%S")
        return _as_output(dt)
    except Exception:
        pass

    # ---------------------------------------------------
    # 1) "DD-Mon HH:MM" or "DD-Mon HH:MMZ" (BPQ, FBB, etc.)
    # Year may be missing; infer from default_year or current year.
    # ---------------------------------------------------
    m = re.match(r"^\s*(\d{1,2})-([A-Za-z]{3})\s+(\d{1,2}):(\d{2})(Z)?\s*$", s)
    if m:
        day = int(m.group(1))
        mon_abbr = m.group(2).title()
        hh = int(m.group(3))
        mi = int(m.group(4))
        year = default_year or datetime.now().year

        try:
            mon = datetime.strptime(mon_abbr, "%b").month
            dt = datetime(year, mon, day, hh, mi, 0)
            return _as_output(dt)
        except Exception:
            pass

    # ---------------------------------------------------
    # 2) "MMDD/HHMM" (some BBS short forms)
    # Year inferred from default_year or current year.
    # ---------------------------------------------------
    m = re.match(r"^\s*(\d{2})(\d{2})/(\d{2})(\d{2})\s*$", s)
    if m:
        mon = int(m.group(1))
        day = int(m.group(2))
        hh = int(m.group(3))
        mi = int(m.group(4))
        year = default_year or datetime.now().year
        try:
            dt = datetime(year, mon, day, hh, mi, 0)
            return _as_output(dt)
        except Exception:
            pass

    # ---------------------------------------------------
    # 3) "DD-Mon" (date only, no time)
    # Year inferred from default_year or current year.
    # ---------------------------------------------------
    m = re.match(r"^\s*(\d{1,2})-([A-Za-z]{3})\s*$", s)
    if m:
        day = int(m.group(1))
        mon_abbr = m.group(2).title()
        year = default_year or datetime.now().year
        try:
            mon = datetime.strptime(mon_abbr, "%b").month
            dt = datetime(year, mon, day, 0, 0, 0)
            return _as_output(dt)
        except Exception:
            pass

    # ---------------------------------------------------
    # 4) Winlink-ish: "YYYY/MM/DD HH:MM" (no seconds)
    # ---------------------------------------------------
    try:
        dt = datetime.strptime(s, "%Y/%m/%d %H:%M")
        return _as_output(dt)
    except Exception:
        pass

    # If nothing matched, optionally log and return None
    if log:
        try:
            log(f"Unrecognized datetime format: {s!r}")
        except Exception:
            pass
    return None
