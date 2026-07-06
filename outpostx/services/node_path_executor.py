# services/node_path_executor.py
"""
Node path executor (UI-friendly worker thread skeleton).

This module provides a Qt-friendly execution wrapper for testing a multi-hop
KA-NODE / NET/ROM routing path (NodePath / NodeHop).

Current status:
- This is intentionally a *skeleton* executor. It focuses on threading and UI
  signaling so the Path Builder / Test Path dialog can be built and exercised.
- The actual transport integration (serial/telnet/ssh) will be wired in later
  via the connection layer (BaseConnection / SendReceiveAdapter / ConnectionController).

Key idea:
- The executor walks NodeHop objects in order and uses success/failure markers to
  decide whether each hop connected successfully before proceeding.

Threading model:
- NodePathExecutor (public QObject) owns a QThread and a private worker QObject.
- The worker emits status/log signals while running in the background thread.
- The executor relays a final finished(ok, summary) signal and cleans up the thread.
"""
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore

from data.node_path_model import NodePath, NodeHop


class NodePathExecutor(QtCore.QObject):
    """
    Qt-friendly controller for executing a NodePath in a worker thread.

    Responsibilities:
      - Own the QThread lifecycle (start/stop/cleanup)
      - Provide UI-facing signals for progress and logging
      - Keep transport and protocol details out of the UI layer

    This class delegates the actual step-by-step work to _NodePathWorker.
    """
    # Human-readable UI outputs
    statusChanged = QtCore.Signal(str)           # e.g., "Connecting to K6KP-7…"
    logLine = QtCore.Signal(str)                 # append to log window
    finished = QtCore.Signal(bool, str)          # ok, summary

    # Optional deeper telemetry (handy later)
    stepChanged = QtCore.Signal(int, str)        # hop_index, node_name
    txLine = QtCore.Signal(str)                  # raw TX line
    rxLine = QtCore.Signal(str)                  # raw RX line

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[_NodePathWorker] = None

    def start(self, path: NodePath) -> None:
        """Start executing the given NodePath in a background QThread.

        If already running, this is a no-op (prevents double-start).

        Args:
        path: The NodePath to execute. A path with no hops is treated as invalid.
        """
        # Prevent double-start
        if self._thread is not None:
            return

        self._thread = QtCore.QThread()
        self._worker = _NodePathWorker(path)

        self._worker.moveToThread(self._thread)

        # Wire worker → public signals
        self._worker.statusChanged.connect(self.statusChanged)
        self._worker.logLine.connect(self.logLine)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.stepChanged.connect(self.stepChanged)
        self._worker.txLine.connect(self.txLine)
        self._worker.rxLine.connect(self.rxLine)

        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def stop(self) -> None:
        """Request that the running worker stop.

        Stop is cooperative: the worker checks a flag between steps.
        Thread teardown is handled when the worker emits finished().
        """
        if self._worker is not None:
            self._worker.request_stop()

    def _on_worker_finished(self, ok: bool, summary: str) -> None:
        """Handle worker completion and tear down the QThread.

        This method always:
          - emits finished(ok, summary)
          - quits and joins the worker thread (best-effort)
          - clears internal references so the executor can be started again
          """
        # propagate to UI
        self.finished.emit(ok, summary)

        # tear down thread
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(1500)
        self._thread = None
        self._worker = None


class _NodePathWorker(QtCore.QObject):
    """
    Background worker that performs the hop-by-hop execution.

    The worker emits progress and log signals and finishes with a boolean
    result + summary. It is designed to be transport-agnostic.
    """
    statusChanged = QtCore.Signal(str)
    logLine = QtCore.Signal(str)
    finished = QtCore.Signal(bool, str)
    stepChanged = QtCore.Signal(int, str)
    txLine = QtCore.Signal(str)
    rxLine = QtCore.Signal(str)

    def __init__(self, path: NodePath) -> None:
        super().__init__()
        self._path = path
        self._stop = False

    def request_stop(self) -> None:
        """Request cooperative cancellation of the path execution."""
        self._stop = True

    @QtCore.Slot()
    def run(self) -> None:
        """
        Execute the NodePath hop-by-hop.

        Current behavior:
          - Simulation only (logs configured hops and emits TX lines).
          - Useful for validating UI wiring and path definitions.

        Future transport integration (TODO):
          - send_line(str)
          - wait_for_any(markers: list[str], timeout_s: float) -> bool
          - connect/disconnect primitives
          - enforce the “connect cmd + maybe next name” rule per NodeHop.use_next_name
        """
        try:
            if self._path.is_empty():
                self.finished.emit(False, "No hops configured.")
                return

            self.statusChanged.emit("Starting path test…")
            self.logLine.emit("== Node Path Test ==")

            # For now, we simply "simulate" the steps so UI plumbing can be tested
            for idx, hop in enumerate(self._path.hops):
                if self._stop:
                    self.finished.emit(False, "Stopped.")
                    return

                self.stepChanged.emit(idx, hop.node_name)
                self.statusChanged.emit(f"Would connect to {hop.node_name}…")
                self.logLine.emit(f"[Hop {idx+1}] Connect to {hop.node_name}")

                # Simulate “success marker” detection by logging configured markers
                if hop.success_markers:
                    self.logLine.emit(f"  success markers: {', '.join(hop.success_markers)}")
                if hop.failure_markers:
                    self.logLine.emit(f"  failure markers: {', '.join(hop.failure_markers)}")

                # Simulate issuing connect cmd to next hop (except last)
                if idx < len(self._path.hops) - 1:
                    nxt = self._path.hops[idx + 1]
                    cmd = hop.connect_cmd.strip()
                    if hop.use_next_name and nxt.node_name:
                        cmd = f"{cmd} {nxt.node_name}".strip()
                    self.txLine.emit(cmd)
                    self.logLine.emit(f"  TX: {cmd}")

            self.statusChanged.emit("Completed (simulation).")
            self.finished.emit(True, "Path test completed (simulation).")
        except Exception as exc:
            self.finished.emit(False, f"Exception: {exc}")
