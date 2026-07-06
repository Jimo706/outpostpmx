# dialogs/send_receive_session_dialog.py
"""Send/Receive Session UI.

Runs SendReceiveSession in a worker thread so the UI stays responsive.

MVP goals:
- Show a live log
- Provide Cancel (cooperative; best effort)
- Close only when finished
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import threading
import traceback

from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid
from PySide6.QtGui import QFont
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QPlainTextEdit

from pathlib import Path
from types import SimpleNamespace
from services.app_info import AppInfo
from services.sr_log_manager import SRLogManager  # new
from ui import theme


@dataclass
class SessionResult:
    """Result summary emitted by the worker when the session ends."""
    ok: bool
    error: Optional[str] = None


class _SendReceiveWorker(QtCore.QObject):
    """Execute a SendReceiveSession on a QThread.

    The session is created via:
        session_factory(logger=..., transcript=..., stop_requested=...)
    """

    logLine = QtCore.Signal(str)
    transcriptLine = QtCore.Signal(str)  # 260102: raw TX/RX transcript
    statusChanged = QtCore.Signal(str)
    finished = QtCore.Signal(object)  # SessionResult
    messagesReceived = QtCore.Signal(object)  # payload: dict


    def __init__(self, session_factory, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._stop_event = threading.Event()
        self._session = None  # set when run() constructs the session

    @QtCore.Slot()
    def run(self) -> None:
        """Entry point executed on the worker thread."""
        try:
            session = self._session_factory(
                logger=self._emit_log,
                transcript=self._emit_transcript,
                stop_requested=self._stop_event.is_set,
                messages_received=self.messagesReceived.emit,
            )
            self._session = session

            self.statusChanged.emit("Starting…")
            session.run()
            self.finished.emit(SessionResult(ok=True))

        except Exception as e:
            tb = traceback.format_exc()
            self._emit_log("ERROR: Send/Receive failed")
            self._emit_log(str(e))
            self._emit_log(tb)
            self.finished.emit(SessionResult(ok=False, error=str(e)))

    """
        # 260317: TEST, TO BE DELETED IF IT WORKS
        def request_stop(self) -> None:
        # Request cooperative stop (best-effort).
        self._stop_event.set()
        self.statusChanged.emit("Cancel requested…")
        # Outpost Classic behavior: force an immediate Abort/Disconnect sequence
        # (e.g., Ctrl-C + CR + D for TAPR) regardless of what the session is doing.
        try:
            if self._session is not None and hasattr(self._session, "abort"):
                self._session.abort()
        except Exception:
            pass
        self._emit_log("Send/Receive: cancel requested")
    """

    def request_stop(self) -> None:
        """
        Request cooperative stop; the session thread performs abort/disconnect.
            UI only requests 'stop', does not call abort()
          * UI thread: only sets the stop flag
          * session thread: sees stop flag and performs abort()
        """
        self._stop_event.set()
        self.statusChanged.emit("Cancel requested…")
        self._emit_log("Send/Receive: cancel requested")


    # ---- internal ----
    def _emit_log(self, line: str) -> None:
        """Emit a log line and (optionally) update the short phase label."""
        short = (line or "").strip()
        if short:
            if len(short) <= 80 and (
                "Send/Receive" in short
                or "Connecting" in short
                or "Retrieving" in short
                or "Sending" in short
            ):
                self.statusChanged.emit(short)
        self.logLine.emit(line)

    def _emit_transcript(self, text: str) -> None:
        """Emit raw transcript chunks (may include newlines)."""
        if text:
            self.transcriptLine.emit(text)


class SendReceiveSessionDialog(QtWidgets.QDialog):
    """
    Modal dialog that runs and monitors a Send/Receive session.

    Public signals:
        statusChanged(str): Forwarded session phase updates (for MainWindow status bar).
        finished(bool): Emitted when the session completes (True) or fails/cancels (False).
    """

    statusChanged = QtCore.Signal(str)
    finished = QtCore.Signal(bool)
    messagesReceived = QtCore.Signal(object)

    def __init__(
        self,
        *,
        session_factory,
        station_label: str = "",
        bbs_label: str = "",
        interface_label: str = "",
        config,
        data_dir: Path | str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config  # geometry support
        self.setWindowTitle("Send/Receive Session")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[_SendReceiveWorker] = None
        self._finished = False
        self._close_requested = False   # need to handle timing with "X" close

        # --- UI ---
        top = QtWidgets.QGridLayout()
        top.setColumnStretch(1, 1)
        top.addWidget(QtWidgets.QLabel("Station:"), 0, 0)
        self.lblStation = QtWidgets.QLabel(station_label)
        top.addWidget(self.lblStation, 0, 1)
        top.addWidget(QtWidgets.QLabel("BBS:"), 1, 0)
        self.lblBbs = QtWidgets.QLabel(bbs_label)
        top.addWidget(self.lblBbs, 1, 1)
        top.addWidget(QtWidgets.QLabel("Interface:"), 2, 0)
        self.lblIface = QtWidgets.QLabel(interface_label)
        top.addWidget(self.lblIface, 2, 1)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate

        phaseRow = QtWidgets.QHBoxLayout()
        phaseRow.addWidget(QtWidgets.QLabel("Phase:"))
        self.lblPhase = QtWidgets.QLabel("Starting…")
        phaseRow.addWidget(self.lblPhase)
        phaseRow.addStretch(1)

        # Two Tabs (Session / Transcript)
        # Session - shows the general progression of the session
        # transcript - shows the client commands & BBS responses
        self.tabs = QtWidgets.QTabWidget()

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        self.transcript = QtWidgets.QPlainTextEdit()
        self.transcript.setReadOnly(True)
        # self.transcript.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)          # no wrap
        self.transcript.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)   # with word wrap
        self.transcript.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        font = QFont()
        font.setFamily("Courier New")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        self.transcript.setFont(font)
        # 260406: Apply transcript style
        self.transcript.setStyleSheet(theme.TRANSCRIPT_STYLE)

        self.tabs.addTab(self.transcript, "Transcript")
        self.tabs.addTab(self.log, "Session")

        # Summary (MVP (Minimum Viable Product) placeholders; wire later)
        summaryRow = QtWidgets.QHBoxLayout()
        self.lblSent = QtWidgets.QLabel("Sent: 0")
        self.lblRecv = QtWidgets.QLabel("Received: 0")
        self.lblSkip = QtWidgets.QLabel("Skipped: 0")
        self.lblErr = QtWidgets.QLabel("Errors: 0")
        for w in (self.lblSent, self.lblRecv, self.lblSkip, self.lblErr):
            summaryRow.addWidget(w)
        summaryRow.addStretch(1)

        btnRow = QtWidgets.QHBoxLayout()
        self.btnCancel = QtWidgets.QPushButton("Cancel")
        self.btnClose = QtWidgets.QPushButton("Close")
        self.btnClose.setEnabled(False)
        btnRow.addStretch(1)
        btnRow.addWidget(self.btnCancel)
        btnRow.addWidget(self.btnClose)

        host = QtWidgets.QVBoxLayout(self)
        host.addLayout(top)
        host.addSpacing(6)
        host.addWidget(self.progress)
        host.addLayout(phaseRow)
        host.addWidget(self.tabs, 1)
        host.addLayout(summaryRow)
        host.addLayout(btnRow)

        # Restore window geometry/state (after UI is constructed)
        if self._config is not None:
            self._config.restore_window_state(self, "SendReceiveSessionDialog")

        self.btnCancel.clicked.connect(self._on_cancel)
        self.btnClose.clicked.connect(self.accept)

        # 260118
        # ---- logging (classic-style daily logs) ----
        self._sr_session_id = self._next_sr_session_id()

        # Determine data_dir (best effort).
        # If AppConfig has a data_dir attribute/property, use it.
        self._data_dir = Path(data_dir).expanduser().resolve()

        # print(f">>> OutpostX data_dir = {data_dir}")

        #260608: expanded services.App_Info module for APP_NAME, APP_VERSION, APP_MARKER
        self._log_mgr = SRLogManager(str(self._data_dir),
                                      app_title=AppInfo.APP_NAME, 
                                      app_version=AppInfo.APP_VERSION, 
                                      marker=AppInfo.APP_MARKER
                                     )


        self._log_mgr.open_for_session(self._sr_session_id)

        # Provide a minimal “snap-like” object for banner details (matches your SRLogManager expectations)
        snap = SimpleNamespace(
            station=SimpleNamespace(name=station_label),
            bbs=SimpleNamespace(name=bbs_label),
            interface=SimpleNamespace(interface_name=interface_label),
        )

        self._log_mgr.write_banner(snap)


        # Start immediately
        self._start(session_factory)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def done(self, result: int) -> None:
        # Save geometry/state on ALL exits (accept/reject/close)
        if self._config is not None:
            self._config.save_window_state(self, "SendReceiveSessionDialog")
        super().done(result)

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------
    def _start(self, session_factory) -> None:
        """
        Create the QThread/worker pair, wire signals, and start the thread.
        close sequence:
        worker finishes → dialog updates/logs finish → thread quits → dialog closes → thread object deleted.
        
        """
        self._thread = QtCore.QThread(self)
        self._worker = _SendReceiveWorker(session_factory)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)

        self._worker.logLine.connect(self._append_log)
        self._worker.transcriptLine.connect(self._append_transcript)
        self._worker.statusChanged.connect(self.lblPhase.setText)
        self._worker.messagesReceived.connect(self.messagesReceived.emit)

        # Forward to main window
        self._worker.statusChanged.connect(self.statusChanged.emit)

        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)

        self._worker.finished.connect(self._worker.deleteLater)

        def _on_thread_finished():
            # result.ok == True   -> close dialog
            # result.ok == False  -> leave dialog open
            if getattr(self, "_last_result_ok", False):
                self.close()

        self._thread.finished.connect(_on_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()


    def _cleanup(self) -> None:
        """Best-effort worker/thread shutdown."""
        if self._worker and not self._finished:
            self._worker.request_stop()

        # QThread may already be deleted (deleteLater); guard with isValid()
        if self._thread and isValid(self._thread):
            try:
                if self._thread.isRunning():
                    self._thread.quit()
                    self._thread.wait(1500)
            except RuntimeError:
                pass

        self._worker = None
        self._thread = None

    # ------------------------------------------------------------------
    # UI slots
    # ------------------------------------------------------------------
    @QtCore.Slot(str)
    def _append_log(self, line: str) -> None:
        self.log.appendPlainText((line or "").rstrip("\n"))
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

        # 260118: ---- Add Logging support ----
        if getattr(self, "_log_mgr", None):
            self._log_mgr.write_session_line(line)

    @QtCore.Slot(str)
    def _append_transcript(self, text: str) -> None:
        # Transcript may include newlines and may not be line-oriented
        self.transcript.moveCursor(QtGui.QTextCursor.End)
        self.transcript.insertPlainText(text)
        sb = self.transcript.verticalScrollBar()
        sb.setValue(sb.maximum())

        # 260118: ---- Add Logging support ----
        if getattr(self, "_log_mgr", None):
            self._log_mgr.write_transcript_chunk(text)

    @QtCore.Slot()
    def _on_cancel(self) -> None:
        if not self._worker or self._finished:
            return
        self.btnCancel.setEnabled(False)
        self._worker.request_stop()

    @QtCore.Slot(object)
    def _on_finished(self, result: SessionResult) -> None:
        self._finished = True
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.btnCancel.setEnabled(False)
        self.btnClose.setEnabled(True)
        self._last_result_ok = bool(result.ok)

        if result.ok:
            self.lblPhase.setText("Completed")
            self._append_log("Send/Receive: finished")
            self.finished.emit(True)
        else:
            self.lblPhase.setText("Failed")
            self.lblErr.setText("Errors: 1")
            self._append_log(f"Send/Receive: failed: {result.error}")
            self.finished.emit(False)

        # 260118: ---- Add Logging support ----
        if getattr(self, "_log_mgr", None):
            self._log_mgr.close()
            self._log_mgr = None

        if getattr(self, "_close_requested", False):
            self.accept()

    # ------------------------------------------------------------------
    # Close behavior
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        """
        On close:
          - Request stop (if running)
          - Quit/wait for the worker thread briefly
          - Allow close to proceed (so app shutdown works)
        """
        if self._thread and isValid(self._thread) and self._thread.isRunning() and not self._finished:
            self._close_requested = True
            self._on_cancel()  # disables Cancel button + requests stop
            self.lblPhase.setText("Cancel requested…")
            event.ignore()
            return

        # Session not running -> normal close
        self._cleanup()

        # 260118: ---- Add Logging support ----
        if getattr(self, "_log_mgr", None):
            self._log_mgr.close()
            self._log_mgr = None

        super().closeEvent(event)

    # ------------------------------------------------------------------
    # SR Logging Helpers
    # ------------------------------------------------------------------
    def _next_sr_session_id(self) -> int:
        """
        Persistent monotonic session counter for log banners.

        Stored in config.settings so it survives restarts and user sessions.
        Reset only when config is reset (fresh install / new config).
        """
        if self._config is None:
            # No config → fall back to 1 (still works, just not persistent)
            return 1

        s = getattr(self._config, "settings", None)
        if s is None:
            return 1

        key = "SendReceive/session_counter"
        cur = s.value(key)
        try:
            cur_i = int(cur) if cur is not None else 0
        except Exception:
            cur_i = 0

        nxt = cur_i + 1
        s.setValue(key, nxt)
        return nxt
