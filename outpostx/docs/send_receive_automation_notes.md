# Send/Receive Automation Notes

## 1. Purpose

OutpostX supports two Send/Receive initiation modes:

1. Manual
2. Interval Scheduling

Manual mode starts a Send/Receive session only when the operator presses the
Send/Receive toolbar/menu action.

Interval Scheduling starts a Send/Receive session automatically every configured
number of minutes.

Valid interval range: 1 to 999 minutes.

---

## 2. High-Level Flow

    Preferences
    ↓
    Send/Receive Settings saved
    ↓
    MainWindow reloads settings
    ↓
    MainWindow applies automation settings
    ↓
    Manual mode: stop timer
    Interval mode: start QTimer
    ↓
    Timer expires
    ↓
    MainWindow starts SendReceiveSessionDialog
    ↓
    Dialog creates worker thread
    ↓
    SendReceiveSession runs
    ↓
    Worker finishes
    ↓
    Thread quits
    ↓
    Dialog closes
    ↓
    MainWindow restarts interval timer

## 3. Main Components
### 1. MainWindow

Owns:

- Send/Receive toolbar action
- automation timer
- countdown state
- launch guard to prevent overlapping sessions
- refresh after Preferences closes

Important fields:

    self._in_session
    self._sendrecv_dialog
    self._auto_sr_timer
    self._countdown_seconds_total
    self._countdown_seconds_left

The dialog should close only after the thread finishes.

    SendReceiveSessionDialog

Owns:

- session window
- worker object
- QThread lifecycle
- session log
- transcript log
- clean close after worker/thread completion

Expected threading pattern:

    self._worker.finished.connect(self._on_finished)
    self._worker.finished.connect(self._thread.quit)
    self._worker.finished.connect(self._worker.deleteLater)

    self._thread.finished.connect(_on_thread_finished)
    self._thread.finished.connect(self._thread.deleteLater)

The dialog should close only after the thread finishes.

SendReceiveSession

Owns the actual non-UI session engine.

Responsibilities:

- snapshot active Station/Tactical/BBS/Interface/settings
- open transport
- login
- send queued messages
- receive inbound messages
- logout
- cleanup

This class is UI-agnostic and is intended to run inside the dialog worker thread.

### 2. Manual Send/Receive Flow

    Operator clicks Send/Receive
    ↓
    MainWindow._on_send_receive()
    ↓
    MainWindow._start_send_receive_session(manual=True)
    ↓
    if _in_session is True:
        return
    ↓
    set _in_session = True
    disable Send/Receive button
    ↓
    create SendReceiveSessionDialog
    ↓
    dialog starts worker thread
    ↓
    SendReceiveSession.run()
    ↓
    session completes
    ↓
    worker emits finished
    ↓
    thread quits
    ↓
    dialog closes
    ↓
    MainWindow._finished()
    ↓
    set _in_session = False
    enable Send/Receive button
    refresh message table
    re-apply automation settings

Manual mode should work even if automation is disabled.

### 3. Interval Scheduling Flow

    Preferences → Send/Receive → Interval, N minutes
    ↓
    Preferences closes
    ↓
    MainWindow._on_setup_preferences()
    ↓
    system_config.refresh_from_repos()
    _on_active_config_changed(...)
    _apply_send_receive_automation_settings()
    ↓
    settings are loaded
    ↓
    if mode == INTERVAL:
        start _auto_sr_timer for N minutes
    else:
        stop _auto_sr_timer

When the interval timer fires:

    _auto_sr_timer.timeout
    ↓
    MainWindow._on_auto_send_receive_timer()
    ↓
    if _in_session:
        return
    ↓
    stop timer
    _start_send_receive_session(manual=False)

When the automated session completes:

    MainWindow._finished()
    ↓
    _in_session = False
    _sendrecv_dialog = None
    Send/Receive button enabled
    message table refreshed
    _apply_send_receive_automation_settings()
    ↓
    timer starts again for next interval

## 4. Required MainWindow Methods
### 1. Manual launcher

    def _on_send_receive(self) -> None:
        self._start_send_receive_session(manual=True)

### 2. Interval timer callback

    def _on_auto_send_receive_timer(self) -> None:
        if self._in_session:
            return

        self._auto_sr_timer.stop()
        self._start_send_receive_session(manual=False)

### 3. Automation settings applier

    def _apply_send_receive_automation_settings(self) -> None:
        try:
            sr = self.system_config.get_send_receive_settings()
        except Exception as exc:
            print(f"WARNING: could not load Send/Receive settings: {exc}")
            sr = None

        mode = (getattr(sr, "automation_mode", "") or "").strip().upper()
        interval_minutes = int(getattr(sr, "interval_minutes", 0) or 0)

        if mode != "INTERVAL":
            self._auto_sr_timer.stop()
            self._countdown_seconds_total = 0
            self._countdown_seconds_left = 0
            self._update_countdown_label()
            return

        interval_minutes = max(1, min(interval_minutes, 999))
        interval_ms = interval_minutes * 60 * 1000

        self._auto_sr_timer.stop()

        self._countdown_seconds_total = interval_minutes * 60
        self._countdown_seconds_left = self._countdown_seconds_total
        self._update_countdown_label()

        if not self._in_session:
            self._auto_sr_timer.start(interval_ms)

## 5. Required SystemConfigService Method

SystemConfigService imports the Send/Receive settings loader.

It should expose this helper:

    def get_send_receive_settings(self):
        return load_send_receive_settings(self._config)

Without this method, MainWindow._apply_send_receive_automation_settings() cannot load the automation mode.

## 6. Important Initialization Order

Do not call:

    self._apply_send_receive_automation_settings()

before _build_statusbar().  The countdown label is created in _build_statusbar() as:

    self.lblCountdown = QtWidgets.QLabel("00:00:00", self)

So the safe order is:

    self._build_menubar()
    self._build_toolbar()
    self._build_statusbar()

    self._apply_send_receive_automation_settings()

Your uploaded MainWindow currently creates the automation timer early in __init__, which is fine, but applying settings before the status bar exists can break countdown handling.

## 7. Preferences Close Hook

MainWindow._on_setup_preferences() should refresh settings after dlg.exec() returns:

    def _on_setup_preferences(self) -> None:
        dlg = SetupDialog(
            self.db_path,
            self.config,
            self.system_config,
            self,
        )

        dlg.exec()

        self.system_config.refresh_from_repos()
        self._on_active_config_changed(self.system_config.get_active_selection())
        self._apply_send_receive_automation_settings()

This belongs in MainWindow, not in SetupDialog.

SetupDialog owns editing/saving preferences. MainWindow owns reacting after Preferences closes.

