# ui/main_window.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, List

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import QUrl
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrinterInfo
from PySide6.QtPrintSupport import QPageSetupDialog  #  REMOVE?
from PySide6.QtGui import QIcon

from app_config import AppConfig

from data.message_dao import MessageDAO
from data.message_repo import MessageRepository, RepoConfig
from data.folder_repo import FolderRepo
from data.message_model import Direction, MessageState, MessageType

from dialogs.about_dialog import AboutDialog
from dialogs.message_form_window import MessageFormWindow, MessageFormMode
from dialogs.form_entry_window import FormEntryWindow   # #164

from services.app_paths import AppPaths
from services.app_info import AppInfo
from services.message_service import MessageService
from services.notification_service import NotificationService
from services.system_config_service import SystemConfigService, ActiveSelection
from services.recent_config_service import RecentConfigService
from services.message_print_service import MessagePrintService, PrintableMessage
from services.desktop_services import (
    open_directory,
    DesktopOpenError,
)
from services.form_definition_loader import (           # #164
    FormDefinition,
    FormRegistry,
)
from services.form_transport import render_form_body    # #164
from services.tool_config import (                      # #171
    ToolConfigError,
    ToolDefinition,
    load_tools,
)
from services.tool_launcher import (                    # #171
    ToolLaunchError,
    launch_tool,
)

from ui.folder_tree_widget import FolderTreeWidget
from ui.message_table_widget import MessageTableWidget
from ui.notification_window import NotificationWindow
from ui.setup_dialog import SetupDialog
from ui.theme import (
    MENU_BAR_STYLE,
    GROUP_BOX_STYLE,
    toolbar_style,
    apply_base_main_window_style,
    apply_tree_style,
    apply_table_style,
    apply_splitter_style,
    primary_toolbutton_style
)

from widgets.message_editor import MessagePayload, TransportMeta


# ----------------------------------------------------------------------
# DB bootstrap helpers
# ----------------------------------------------------------------------
def ensure_folders_table_and_roots(dao: MessageDAO) -> None:
    """Create core tables/views idempotently and seed root folders."""
    with dao._connect() as conn:
        # messages + bodies
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                msgidx        INTEGER PRIMARY KEY AUTOINCREMENT,
                bbs_call      TEXT,
                bbsmsgno      TEXT,
                from_call     TEXT,
                to_call       TEXT,
                subject       TEXT,
                messagelen    INTEGER DEFAULT 0,
                sent_at       TEXT,
                rcvd_at       TEXT,
                mstate        TEXT NOT NULL,         -- NEW/DRAFT/QUEUED/SENT/RECEIVED
                direction     TEXT NOT NULL,         -- INBOUND/OUTBOUND
                is_read       INTEGER NOT NULL DEFAULT 0,
                is_deleted    INTEGER NOT NULL DEFAULT 0,
                is_urgent     INTEGER NOT NULL DEFAULT 0,
                is_encoded    INTEGER NOT NULL DEFAULT 0,
                is_locked     INTEGER NOT NULL DEFAULT 0,
                is_msgdelreq  INTEGER NOT NULL DEFAULT 0,
                has_attachment INTEGER NOT NULL DEFAULT 0,
                header        TEXT,
                folderidx     INTEGER NOT NULL REFERENCES folders(folderidx)
                                  ON UPDATE CASCADE ON DELETE RESTRICT,
                mtype         INTEGER NOT NULL DEFAULT 0,   -- MessageType enum
                messageid     TEXT,                         -- local MID (CUP-102P)
                formtype      TEXT NOT NULL DEFAULT 'PLAIN',
                recvmsgid     TEXT,
                is_rdr        INTEGER NOT NULL DEFAULT 0,   -- delivery receipt requested
                is_rrr        INTEGER NOT NULL DEFAULT 0    -- read receipt received
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_bodies (
                msgidx     INTEGER PRIMARY KEY
                              REFERENCES messages(msgidx)
                              ON UPDATE CASCADE ON DELETE CASCADE,
                message    TEXT
            );
            """
        )
        conn.execute("DROP VIEW IF EXISTS v_messages_full;")
        conn.execute(
            """
            CREATE VIEW v_messages_full AS
            SELECT
                m.msgidx,
                m.bbs_call, m.bbsmsgno,
                m.from_call, m.to_call,
                m.subject, m.messagelen,
                m.sent_at, m.rcvd_at,
                m.mstate, m.direction,
                m.is_read, m.is_deleted, m.is_urgent, m.is_encoded, m.is_locked,
                m.is_msgdelreq, m.has_attachment,
                m.header, m.folderidx,
                m.mtype, m.messageid, m.formtype, m.recvmsgid,
                m.is_rdr, m.is_rrr,
                b.message AS body
            FROM messages m
            LEFT JOIN message_bodies b ON b.msgidx = m.msgidx;
            """
        )
        conn.commit()

    # folders + seed roots
    with dao._connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS folders (
                folderidx   INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                parentidx   INTEGER REFERENCES folders(folderidx)
                              ON UPDATE CASCADE ON DELETE RESTRICT,
                UNIQUE(name, parentidx)
            );
            """
        )
        for name in ("Inbox", "Outbox", "Sent", "Drafts", "Trash"):
            conn.execute(
                """
                INSERT INTO folders (name, parentidx)
                SELECT ?, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM folders WHERE name=? AND parentidx IS NULL
                )
                """,
                (name, name),
            )
        conn.commit()


def list_root_folders(dao: MessageDAO) -> List[tuple[str, int]]:
    with dao._connect() as conn:
        rows = conn.execute(
            "SELECT folderidx, name FROM folders WHERE parentidx IS NULL ORDER BY name"
        ).fetchall()
        return [(r["name"], int(r["folderidx"])) for r in rows]


MRU_DEFAULT_LIMIT = 8

# ----------------------------------------------------------------------
# Main Window
# ----------------------------------------------------------------------
class MainWindow(QtWidgets.QMainWindow):
    """
    Main OutpostX window

    - Left: FolderTreeWidget
    - Right: MessageTableWidget (table + preview)
    - Menu + toolbar
    - Geometry/state persistence via AppConfig
    - Integrates compose/view dialogs via MessageService
    """

    # Emitted when the countdown reaches zero (for future SessionManager)
    sessionCountdownElapsed = QtCore.Signal()

    def __init__(
        self,
        db_path: Path,
        config: AppConfig,
        message_service: MessageService,
        system_config: SystemConfigService,
        notification_service: NotificationService,
        recent_config_service: RecentConfigService,
        app_paths=None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:

        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.setWindowIcon(QIcon(AppPaths.app_icon()))

        self.apptitle = AppInfo.TITLE
        self.appversion = AppInfo.APP_VERSION
        self.setWindowTitle(f"{self.apptitle}    v{self.appversion}")

        self._message_forms: list[QtWidgets.QMainWindow] = []

        self.db_path = db_path

        self.config = config
        self.message_service = message_service
        self.system_config = system_config
        self.paths = app_paths
        self.recent_config_service = recent_config_service

        # Forms Engine #164
        self.form_registry = FormRegistry(self.paths.forms_dir)
        self.form_registry.reload()

        # --- Set up Notification Service ---
        self.notification_service = notification_service
        self.notification_window: NotificationWindow | None = None

        # --- Status bar related state (init early) ---
        self._status_legal_call: str | None = None
        self._status_tactical_call: str | None = None
        self._status_bbs_name: str | None = None
        self._status_interface_name: str | None = None
        self._system_status_text: str = "no configuration selected"
        self._session_status_text: str = ""
        self._in_session: bool = False

        # 260426: add S/R interval automation
        self._sendrecv_dialog = None
        self.sessionCountdownElapsed.connect(self._on_auto_send_receive_timer)
        # 260426: end  S/R interval automation

        # Initialize play sound on msg receipt
        self._receive_sound = QSoundEffect(self)
        self._receive_sound.setVolume(0.5)   # 0.0 – 1.0

        # Countdown
        self._countdown_seconds_total: int = 0
        self._countdown_seconds_left: int = 0
        self._countdown_timer = QtCore.QTimer(self)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        # Clock
        self._clock_timer: QtCore.QTimer | None = None

        # --- Data layer ---
        self.dao = MessageDAO(db_path)
        ensure_folders_table_and_roots(self.dao)

        self.repo_cfg = RepoConfig()
        self.msg_repo = MessageRepository(self.dao, self.repo_cfg)
        self.folder_repo = FolderRepo(db_path)

        roots = dict(list_root_folders(self.dao))
        self.repo_cfg.default_inbound_folderidx = roots.get("Inbox", next(iter(roots.values()), 1))
        self.repo_cfg.default_outbound_folderidx = roots.get(
            "Outbox", self.repo_cfg.default_inbound_folderidx
        )

        apply_base_main_window_style(self)  # 260327 ui.theme.py

        # --- Central UI ---
        central = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(6, 6, 6, 6)
        self.setCentralWidget(central)

        self.labelHeader = QtWidgets.QLabel("OutpostX — Message Manager", central)
        f = self.labelHeader.font()
        f.setPointSize(10)
        self.labelHeader.setFont(f)
        v.addWidget(self.labelHeader)

        # splitter: left tree | right table+preview
        self.splitMain = QtWidgets.QSplitter(QtCore.Qt.Horizontal, central)
        apply_splitter_style(self.splitMain)
        v.addWidget(self.splitMain, 1)

        # NOTE: create widgets without parent; add to splitter
        self.folderTree = FolderTreeWidget()
        self.msgTable = MessageTableWidget()
        self.splitMain.addWidget(self.folderTree)
        self.splitMain.addWidget(self.msgTable)
        self.splitMain.setStretchFactor(0, 0)
        self.splitMain.setStretchFactor(1, 1)
        self.folderTree.setMinimumWidth(180)

        # 260327, ui.theme.py
        apply_tree_style(self.folderTree)
        apply_table_style(self.msgTable)

        # Wire repos/settings
        self.folderTree.setRepository(self.folder_repo)
        self.folderTree.setSettings(self.config.settings, "FolderTree")

        self.msgTable.setRepository(self.msg_repo)
        self.msgTable.setSettings(self.config.settings, "MessageTable")

        """
        # TODO(UI): MessageTableWidget is a composite widget.
        # Compact row styling (remove grid / padding) requires changes inside
        # MessageTableWidget rather than MainWindow. Deferred intentionally.
        """

        # Menus / toolbar / status
        self._build_actions()
        self._build_menubar()
        self._build_toolbar()
        self._build_statusbar()

        # 260426: move here after statusbar built
        self._apply_send_receive_automation_settings()

        # Hook system config → status bar
        self.system_config.activeConfigChanged.connect(self._on_active_config_changed)
        self._on_active_config_changed(self.system_config.get_active_selection())

        # Signals
        self.folderTree.folderSelected.connect(self.msgTable.setFolder)
        self.folderTree.moveMessagesRequested.connect(self._on_messages_moved)

        # Message table: use the high-level signal that gives us msgidx
        self.msgTable.messageDoubleClicked.connect(self._on_message_double_clicked)

        # Build initial folder list and restore state
        self.folderTree.refresh()
        self._restore_window_state()

        # --------------------------------------------------------------
        # #101, 260816: Startup folder preference
        #
        # If "Start in Inbox" is enabled, always open Inbox.
        # Otherwise preserve the previously selected folder and fall
        # back to Inbox if no previous folder exists.
        # --------------------------------------------------------------
        start_in_inbox = self.config.settings.value(
            "General/start_in_inbox",
            False,
            type=bool,
        )

        current = None

        if start_in_inbox:
            initial = self.repo_cfg.default_inbound_folderidx

            # Force the Folder Tree selection to Inbox as well.
            self.folderTree.select_folder(initial)      # 101, 260816

        else:
            if hasattr(self.folderTree, "current_folderidx"):
                current = self.folderTree.current_folderidx()

            initial = current or self.repo_cfg.default_inbound_folderidx

        # Keep folder selector and message table synchronized
        self._select_folder_in_combo(initial)
        self.msgTable.setFolder(initial)
        self.msgTable.view.sortByColumn(
            7,
            QtCore.Qt.SortOrder.DescendingOrder,
        )


        # 260514, P134 
        # Add an open-window holder for dialogs.message_form_window.py
        self._message_forms = []


    def keyPressEvent(self, event: QtCore.QEvent) -> None:
        """
        Handle global key shortcuts for the main window.

        Deal with the user pressing ESC to close the application.
        """
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()  # triggers closeEvent()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_actions(self) -> None:
        # File Actions
        self.action_export_all = QtGui.QAction("Export &All messages…", self)
        self.action_export_folder = QtGui.QAction("Export &This folder…", self)
        self.action_import = QtGui.QAction("&Import…", self)

        self.action_print_setup = QtGui.QAction("Print Set&up…", self)
        self.action_print_preview = QtGui.QAction("Print Pre&view…", self)
        self.action_print = QtGui.QAction("&Print…", self)
        self.action_print.setShortcut("Ctrl+P")
        self.action_print_no_headers = QtGui.QAction("Print, &No Headers…", self)

        self.action_delete_all = QtGui.QAction("&Delete all messages", self)
        self.action_delete_all.setShortcut("Shift+Del")
        self.action_exit = QtGui.QAction("E&xit", self)
        self.action_exit.setShortcut("Ctrl+Q")

        # Setup Actions
        self.action_setup_preferences = QtGui.QAction("&Preferences…", self)

        # Main Actions
        self.action_new = QtGui.QAction("&New", self)
        self.action_new.setShortcut("Ctrl+N")
        self.action_open_data_dir = QtGui.QAction("Open Data Directory", self)

        # Help Actions
        self.action_about = QtGui.QAction("&About", self)

        #Tool Bar Actions
        self.folder_combo = QtWidgets.QComboBox(self)
        self.action_refresh = QtGui.QAction("Refresh", self)
        self.action_send_receive = QtGui.QAction("Send/Receive", self)
        self.action_font_larger = QtGui.QAction("A+", self)
        self.action_font_smaller = QtGui.QAction("A−", self)

        self.action_notifications = QtGui.QAction("&Notifications", self)
        self.action_notifications.triggered.connect(self._on_notifications)

        # Menu Wiring
        self.action_exit.triggered.connect(self.close)
        self.action_delete_all.triggered.connect(self.on_delete_all)
        self.action_import.triggered.connect(self.on_import)
        self.action_export_all.triggered.connect(self.on_export_all)
        self.action_export_folder.triggered.connect(self.on_export_folder)

        self.action_print_setup.triggered.connect(self.on_print_setup)
        self.action_print_preview.triggered.connect(self.on_print_preview)
        self.action_print.triggered.connect(self.on_print)
        self.action_print_no_headers.triggered.connect(self.on_print_no_headers)

        self.action_setup_preferences.triggered.connect(self._on_setup_preferences)
        self.action_new.triggered.connect(self.on_new_message)
        self.action_about.triggered.connect(self.on_help_about)
        self.action_open_data_dir.triggered.connect(self._open_data_directory)

        # Toolbar Wiring
        self.folder_combo.currentIndexChanged.connect(self._on_folder_combo_changed)
        self.action_refresh.triggered.connect(self.msgTable.refresh)
        self.action_send_receive.triggered.connect(self._on_send_receive)
        self.action_print.triggered.connect(self.on_print)
        self.action_font_larger.triggered.connect(self.msgTable.increaseFont)
        self.action_font_smaller.triggered.connect(self.msgTable.decreaseFont)


    # ------------------------------------------------------------------
    # Menus / toolbar
    # ------------------------------------------------------------------
    def _build_menubar(self) -> None:

        mb = self.menuBar()
        mb.setStyleSheet(MENU_BAR_STYLE)    # 260327, ui.theme.py

        m_file = mb.addMenu("&File")
        m_file.addAction(self.action_new)
        m_file.addSeparator()

        export_menu = m_file.addMenu("&Export")
        export_menu.addAction(self.action_export_all)
        export_menu.addAction(self.action_export_folder)
        m_file.addAction(self.action_import)
        m_file.addSeparator()

        self.mru_menu = m_file.addMenu("Most &Recently Used")
        self._rebuild_mru_menu()
        m_file.addSeparator()

        ## m_file.addAction(self.action_print_setup)    # does not work as implemented
        # File Menu
        m_file.addAction(self.action_print_preview)
        m_file.addAction(self.action_print)
        m_file.addAction(self.action_print_no_headers)
        m_file.addSeparator()
        m_file.addAction(self.action_delete_all)
        m_file.addSeparator()
        m_file.addAction(self.action_exit)

        # Setup Menu
        m_setup = mb.addMenu("&Setup")
        m_setup.addAction(self.action_setup_preferences)

        # Notification Functions
        m_view = mb.addMenu("&View")
        m_view.addAction(self.action_notifications)

        # Forms Menu    #164
        self.forms_menu = mb.addMenu("F&orms")
        self._rebuild_forms_menu()

        # Tools Menu    #171
        self.tools_menu = mb.addMenu("&Tools")
        self._rebuild_tools_menu()        

        # Actions Menu
        m_actions = mb.addMenu("&Actions")
        m_actions.addAction(self.action_new)
        m_actions.addAction(self.action_open_data_dir)

        # Help Menu
        m_help = mb.addMenu("&Help")
        m_help.addAction(self.action_about)


    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Main")
        tb.setObjectName("MainToolbar")
        tb.setStyleSheet(toolbar_style("MainToolbar"))  # 260327, ui.theme.py
        tb.setMovable(False)

        self._folders = list_root_folders(self.dao)  # [(name, id)]
        for name, _fid in self._folders:
            self.folder_combo.addItem(name)
        tb.addWidget(QtWidgets.QLabel("Folder: "))
        tb.addWidget(self.folder_combo)

        tb.addSeparator()
        tb.addAction(self.action_new)
        tb.addSeparator()
        tb.addAction(self.action_refresh)
        tb.addAction(self.action_send_receive)
        tb.addAction(self.action_print)
        tb.addAction(self.action_font_larger)
        tb.addAction(self.action_font_smaller)
        
        self._update_print_tooltip()    # set the Printer Tool Tip to the default printer

        # Get the actual QToolButton created by Qt.  This makes the
        # Send/Receive button slightly filled + stronger border + bold text
        btn_sendrec = tb.widgetForAction(self.action_send_receive)
        if btn_sendrec:
            btn_sendrec.setObjectName("SendReceiveButton")
            btn_sendrec.setStyleSheet(primary_toolbutton_style("SendReceiveButton"))


    # ------------------------------------------------------------------
    # Status bar (3 zones)
    # ------------------------------------------------------------------
    def _build_statusbar(self) -> None:
        """
        Build a 3-zone status bar:

          [ General status (config/session) ] [Countdown HH:MM:SS] [Clock HH:MM:SS]
        """
        self.statusbar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self.statusbar)

        # Left: general status
        self.lblStatusGeneral = QtWidgets.QLabel(self)
        self.lblStatusGeneral.setText(self._system_status_text)
        self.lblStatusGeneral.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        # Right: countdown + clock (fixed-width, monospaced-ish)
        mono_font = self.font()
        mono_font.setStyleHint(QtGui.QFont.Monospace)
        mono_font.setFamily("Courier New")  # falls back harmlessly if missing

        self.lblCountdown = QtWidgets.QLabel("00:00:00", self)
        self.lblCountdown.setFont(mono_font)
        self.lblCountdown.setMinimumWidth(self._time_label_width())
        self.lblCountdown.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.lblClock = QtWidgets.QLabel("00:00:00", self)
        self.lblClock.setFont(mono_font)
        self.lblClock.setMinimumWidth(self._time_label_width())
        self.lblClock.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        # Layout: general status stretches, countdown + clock are permanent widgets on the right
        self.statusbar.addWidget(self.lblStatusGeneral, 1)
        self.statusbar.addPermanentWidget(self.lblCountdown)
        self.statusbar.addPermanentWidget(self.lblClock)

        # Start clock timer
        self._clock_timer = QtCore.QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        # Init countdown (manual/off)
        self._update_countdown_label()

    def _time_label_width(self) -> int:
        """Return a reasonable fixed width in pixels for 'HH:MM:SS'."""
        fm = QtGui.QFontMetrics(self.font())
        return fm.horizontalAdvance("00:00:00") + 12

    # ------------------------------------------------------------------
    # General status (system configuration vs session status)
    # ------------------------------------------------------------------
    def set_system_configuration(
        self,
        legal_call: str | None,
        tactical_call: str | None,
        bbs_name: str | None,
        interface_name: str | None,
    ) -> None:
        """
        Update the "system configuration" part of the status bar.

        - legal_call: station's legal callsign (e.g., 'KN6PE')
        - tactical_call: optional tactical (e.g., 'CUPEOC'); shown as 'KN6PE as CUPEOC'
        - bbs_name: BBS friendly name (e.g., 'SCC W1 BBS'); 'BBS not set' if None/empty
        - interface_name: interface label (e.g., 'W1-Telnet(telnet)'); 'IF not set' if None/empty
        """
        self._status_legal_call = (legal_call or "").strip().upper() or None
        self._status_tactical_call = (tactical_call or "").strip().upper() or None
        self._status_bbs_name = (bbs_name or "").strip() or None
        self._status_interface_name = (interface_name or "").strip() or None

        self._system_status_text = self._build_system_status_text()

        # Only show system configuration when no session is in progress
        if not self._in_session:
            self.lblStatusGeneral.setText(self._system_status_text)

    def _build_system_status_text(self) -> str:
        """
        Build something like:
           'KN6PE as CUPEOC -- SCC W1 BBS -- W1-Telnet(telnet)'

        Fallbacks:
           - no config at all -> 'no configuration selected'
           - missing call     -> 'Call Sign not set'
           - missing BBS      -> 'BBS not set'
           - missing IF       -> 'IF not set'
        """
        has_any = any(
            [
                self._status_legal_call,
                self._status_tactical_call,
                self._status_bbs_name,
                self._status_interface_name,
            ]
        )
        if not has_any:
            return "no configuration selected"

        # 1) Call (with optional tactical)
        if self._status_legal_call:
            call_piece = self._status_legal_call
            if self._status_tactical_call:
                call_piece += f" as {self._status_tactical_call}"
        else:
            call_piece = "Call Sign not set"

        # 2) BBS
        bbs_piece = self._status_bbs_name or "BBS not set"

        # 3) Interface
        if_piece = self._status_interface_name or "IF not set"

        # Spec: "Each is separated by a double-hyphen."
        return f"{call_piece} -- {bbs_piece} -- {if_piece}"

    # Session-status overlay
    def show_session_status(self, text: str) -> None:
        """
        Temporarily override the general status with a short session status string.

        Examples:
          'Connecting to W1-Telnet(telnet)…'
          'Sending message \"ICS-213 to CUPEOC\"'
          'Retrieving NTS messages…'
        """
        self._session_status_text = text
        self._in_session = True
        self.lblStatusGeneral.setText(text)

    def clear_session_status(self) -> None:
        """
        Clear session status and return to system configuration display.
        Call when a Send/Receive session ends.
        """
        self._session_status_text = ""
        self._in_session = False
        self.lblStatusGeneral.setText(self._system_status_text)

    # ------------------------------------------------------------------
    # Countdown timer helpers for Session Automation
    # ------------------------------------------------------------------
    def configure_session_automation(self, enabled: bool, interval_seconds: int) -> None:
        """
        Configure the countdown timer for 'Session Automation'.

        - enabled=False -> manual mode; label shows '00:00:00'
        - enabled=True  -> starts/arms a countdown from interval_seconds
        """
        if not enabled or interval_seconds <= 0:
            self._countdown_seconds_total = 0
            self._countdown_seconds_left = 0
            if self._countdown_timer:
                self._countdown_timer.stop()
            self._update_countdown_label()
            return

        # enable & arm
        self._countdown_seconds_total = int(interval_seconds)
        self._countdown_seconds_left = int(interval_seconds)

        if self._countdown_timer is None:
            self._countdown_timer = QtCore.QTimer(self)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_timer.start(1000)
        self._update_countdown_label()

    def restart_countdown(self) -> None:
        """
        Restart the countdown from the configured total.
        Useful after a session run in 'every N minutes' mode.
        """
        if self._countdown_seconds_total <= 0:
            return
        self._countdown_seconds_left = self._countdown_seconds_total
        if self._countdown_timer is None:
            self._countdown_timer = QtCore.QTimer(self)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_timer.start(1000)
        self._update_countdown_label()

    def stop_countdown(self) -> None:
        """Stop countdown but leave the last displayed value."""
        if self._countdown_timer:
            self._countdown_timer.stop()

    def _on_countdown_tick(self) -> None:
        if self._countdown_seconds_left > 0:
            self._countdown_seconds_left -= 1
            self._update_countdown_label()

        if self._countdown_seconds_left <= 0:
            # Hit zero → stop and notify
            if self._countdown_timer:
                self._countdown_timer.stop()
            self._countdown_seconds_left = 0
            self._update_countdown_label()
            self.sessionCountdownElapsed.emit()

    def _update_countdown_label(self) -> None:
        secs = max(0, int(self._countdown_seconds_left))
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        self.lblCountdown.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # ------------------------------------------------------------------
    # System clock (24-hr HH:MM:SS)
    # ------------------------------------------------------------------
    def _update_clock(self) -> None:
        """
        Update system clock label once per second.

        TODO: later, add a config toggle for local vs UTC time.
        """
        # Local time for now; change to .utcnow() for UTC.
        now = QtCore.QDateTime.currentDateTime()
        # 24-hour HH:MM:SS
        self.lblClock.setText(now.toString("HH:mm:ss"))

    # ------------------------------------------------------------------
    # Folder helpers
    # ------------------------------------------------------------------
    def _on_folder_combo_changed(self, combo_index: int) -> None:
        _, fid = self._folders[combo_index]
        self.msgTable.setFolder(fid)
        self.msgTable.view.sortByColumn(7, QtCore.Qt.SortOrder.DescendingOrder)

    def _select_folder_in_combo(self, folderidx: int) -> None:
        idx = 0
        for i, (_, fid) in enumerate(self._folders):
            if fid == folderidx:
                idx = i
                break
        self.folder_combo.setCurrentIndex(idx)

    def _restore_window_state(self) -> None:
        self.config.restore_window_state(self, "MainWindow")
        s = self.config.settings.value("MainWindow/splitter/h")
        if s:
            self.splitMain.restoreState(s)

    # ------------------------------------------------------------------
    # Active Config Helper
    # ------------------------------------------------------------------
    def _on_active_config_changed(self, selection: ActiveSelection) -> None:
        """
        Called whenever the active Station/Tactical/BBS/Interface changes.

        We convert this into the status bar's 'system configuration' string.
        """
        # Combine legal + tactical exactly per your status bar spec:
        #   KN6PE
        #   KN6PE as CUPEOC
        legal = selection.legal_call
        tactical = selection.tactical_call

        self.set_system_configuration(
            legal_call=legal,
            tactical_call=tactical,
            bbs_name=selection.bbs_name,
            interface_name=selection.interface_name,
        )

    # ------------------------------------------------------------------
    # MRU Helper
    # ------------------------------------------------------------------
    # Load MRU
    def _load_mru_entries(self) -> list[dict]:
        return self.recent_config_service.load()

    # Save MRU
    def _save_mru_entries(self, entries: list[dict]) -> None:
        self.recent_config_service.save(entries)

    # Build current MRU entry
    def _current_mru_entry(self) -> dict | None:
        sel = self.system_config.get_active_selection()
        if not sel:
            return None

        if not sel.station_id or not sel.bbs_id or not sel.interface_id:
            return None

        user = (sel.tactical_call or sel.legal_call or "").strip().upper()
        bbs = (sel.bbs_name or sel.bbs_call or "").strip()
        iface = (sel.interface_name or "").strip()

        if not user or not bbs or not iface:
            return None

        return {
            "station_id": sel.station_id,
            "tactical_id": sel.tactical_id,
            "bbs_id": sel.bbs_id,
            "interface_id": sel.interface_id,
            "user": user,
            "bbs": bbs,
            "interface": iface,
        }

    # MRU key for de-dupe
    def _mru_identity_key(self, entry: dict) -> tuple:
        return (
            entry.get("station_id"),
            entry.get("tactical_id"),
            entry.get("bbs_id"),
            entry.get("interface_id"),
        )

    # Record current active config
    def _record_active_config_mru(self) -> None:
        entry = self._current_mru_entry()
        if not entry:
            return

        entries = self._load_mru_entries()
        key = self._mru_identity_key(entry)

        entries = [
            e for e in entries
            if self._mru_identity_key(e) != key
        ]

        entries.insert(0, entry)
        entries = entries[:MRU_DEFAULT_LIMIT]

        self._save_mru_entries(entries)
        self._rebuild_mru_menu()

    # Rebuild File menu submenu
    def _rebuild_mru_menu(self) -> None:
        if not hasattr(self, "mru_menu"):
            return

        self.mru_menu.clear()
        entries = self._load_mru_entries()

        if not entries:
            action = self.mru_menu.addAction("(No recent configurations)")
            action.setEnabled(False)
            return

        for entry in entries[:MRU_DEFAULT_LIMIT]:
            user = entry.get("user") or "?"
            bbs = entry.get("bbs") or "?"
            iface = entry.get("interface") or "?"
            label = f"{user} | {bbs} | {iface}"

            action = self.mru_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, e=entry: self._activate_mru_entry(e)
            )

    # Activate selected MRU
    def _activate_mru_entry(self, entry: dict) -> None:
        try:
            station_id = entry.get("station_id")
            tactical_id = entry.get("tactical_id")
            bbs_id = entry.get("bbs_id")
            interface_id = entry.get("interface_id")

            self.system_config.set_active_combination(
                station_id=station_id,
                tactical_id=tactical_id,
                bbs_id=bbs_id,
                interface_id=interface_id,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Most Recently Used",
                f"Unable to activate this recent configuration:\n{exc}",
            )
            return

        self._record_active_config_mru()

    # ------------------------------------------------------------------
    # Forms Engine  #164
    # ------------------------------------------------------------------
    def _rebuild_forms_menu(self) -> None:
        """
        Rebuild the Forms menu from all valid .opxform definitions.
        """
        if not hasattr(self, "forms_menu"):
            return

        self.forms_menu.clear()

        forms = self.form_registry.forms()

        if not forms:
            action = self.forms_menu.addAction("(No forms installed)")
            action.setEnabled(False)
        else:
            for form in forms:
                action = self.forms_menu.addAction(form.name)
                action.triggered.connect(
                    lambda checked=False, f=form: self._on_form_selected(f)
                )

        self.forms_menu.addSeparator()

        reload_action = self.forms_menu.addAction("&Reload Forms")
        reload_action.triggered.connect(self._reload_forms)


    def _reload_forms(self) -> None:
        """
        Rescan the Forms directory and rebuild the menu.
        """
        forms = self.form_registry.reload()
        self._rebuild_forms_menu()

        errors = self.form_registry.errors

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Reload Forms",
                "One or more form definitions could not be loaded:\n\n"
                + "\n".join(errors),
            )
            return

        self.statusbar.showMessage(
            f"Loaded {len(forms)} form(s).",
            3000,
        )


    def _on_form_selected(self, form: FormDefinition) -> None:
        """ #164, 260821
        Open the generic OPXFORM entry window.
        """
        dlg = FormEntryWindow(
            form=form,
            parent=self,
        )

        dlg.messageRequested.connect(self._on_form_message_requested)
        dlg.exec()


    def _resolve_form_subject(
        self,
        form: FormDefinition,
        values: dict,
    ) -> str:
        """  #164, 260827
        Resolve the initial Outpost packet Subject from the OPXFORM
        definition.

        Supported rules:

            source = "field"
                Use the current value of the named form field.

            source = "fixed"
                Use the literal text supplied by the form definition.

        For backward compatibility, a form without an input.subject
        rule falls back to the historical field id "subject".
        """
        subject_def = form.input.get("subject")

        if not isinstance(subject_def, dict):
            return str(
                values.get("subject", "") or ""
            ).strip()

        source = str(
            subject_def.get("source", "") or ""
        ).strip().lower()

        value = str(
            subject_def.get("value", "") or ""
        ).strip()

        if source == "field":
            return str(
                values.get(value, "") or ""
            ).strip()

        if source == "fixed":
            return value

        return ""


    def _on_form_message_requested(
        self,
        form: FormDefinition,
        values: dict,
    ) -> None:
        """
        Convert completed OPXFORM data into a normal Outpost message
        and open the standard Message Form for packet addressing.
        """
        try:
            body = render_form_body(form, values)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Forms Engine",
                f"Unable to create the form message:\n\n{exc}",
            )
            return

        # The served-agency Subject becomes the initial Outpost subject.
        # MessageFormWindow remains responsible for normal Outpost envelope
        # defaults such as BBS, From, To, MID settings, etc.
        subject = self._resolve_form_subject(form, values)

        active_bbs = self.system_config.get_active_bbs()

        bbs_name = ""
        if active_bbs is not None:
            bbs_name = (
                (getattr(active_bbs, "connect_call", "") or "").strip()
                or (getattr(active_bbs, "bbs_call", "") or "").strip()
            )

        try:
            from_call = self.system_config.get_default_from_call()
        except Exception:
            from_call = ""

        payload = MessagePayload(
            bbs_name=bbs_name,
            from_call=from_call,
            to_call="",
            subject=subject,
            body=body,
            type="private",
            urgent=False,
            req_delivery_rcpt=False,
            req_read_rcpt=False,
            base64_encode=False,
        )

        win = MessageFormWindow(
            mode=MessageFormMode.NEW,
            service=self.message_service,
            system_config=self.system_config,
            config=self.config,
            payload=payload,
            parent=self,
        )

        win.saved.connect(lambda mid: self._after_compose_change(mid))
        win.sent.connect(lambda mid: self._after_compose_change(mid))
        win.deleted.connect(lambda mid: self._after_compose_deleted(mid))

        self._track_message_form(win)
        win.show()

    # ------------------------------------------------------------------
    # Tools Menu  #171
    # ------------------------------------------------------------------
    def _rebuild_tools_menu(self) -> None:
        """
        Rebuild the Tools menu from:

            <DataDir>/tools.json
            <DataDir>/user_tools.json

        Supplied tools are shown first. User-added tools are shown after
        a separator.
        """
        if not hasattr(self, "tools_menu"):
            return

        self.tools_menu.clear()

        if self.paths is None:
            action = self.tools_menu.addAction(
                "(Tools configuration unavailable)"
            )
            action.setEnabled(False)
            return

        try:
            tools = load_tools(
                self.paths.data_dir
            )

        except ToolConfigError as exc:
            action = self.tools_menu.addAction(
                "(Unable to load tools)"
            )
            action.setEnabled(False)

            QtWidgets.QMessageBox.warning(
                self,
                "Tools",
                str(exc),
            )
            return

        system_tools = [
            tool
            for tool in tools
            if tool.source == "system"
        ]

        user_tools = [
            tool
            for tool in tools
            if tool.source == "user"
        ]

        if not tools:
            action = self.tools_menu.addAction(
                "(No tools configured)"
            )
            action.setEnabled(False)

        for tool in system_tools:
            self._add_tool_action(tool)

        if system_tools and user_tools:
            self.tools_menu.addSeparator()

        for tool in user_tools:
            self._add_tool_action(tool)

        self.tools_menu.addSeparator()

        reload_action = self.tools_menu.addAction(
            "&Reload Tools"
        )
        reload_action.triggered.connect(
            self._reload_tools
        )


    def _add_tool_action(
        self,
        tool: ToolDefinition,
    ) -> None:
        action = self.tools_menu.addAction(
            tool.name
        )

        action.setStatusTip(
            f"Launch {tool.name}"
        )

        action.triggered.connect(
            lambda checked=False, t=tool:
                self._launch_configured_tool(t)
        )


    def _reload_tools(self) -> None:
        """
        Reload tools.json/user_tools.json and rebuild the Tools menu.
        """
        self._rebuild_tools_menu()

        self.statusbar.showMessage(
            "Tools configuration reloaded.",
            3000,
        )


    def _launch_configured_tool(
        self,
        tool: ToolDefinition,
    ) -> None:
        """
        Launch a configured external tool.
        """
        if self.paths is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Tools",
                "The OutpostX program directory is not available.",
            )
            return

        try:
            launch_tool(
                tool,
                program_dir=self.paths.program_dir,
            )

        except ToolLaunchError as exc:
            QtWidgets.QMessageBox.warning(
                self,
                tool.name,
                str(exc),
            )
            return

        self.statusbar.showMessage(
            f"Launched {tool.name}.",
            3000,
        )

    # ------------------------------------------------------------------
    # Double-click behavior (edit vs view)
    # ------------------------------------------------------------------
    def _on_message_double_clicked(self, msgidx: int) -> None:
        """Dispatch double-click based on direction/state."""
        got = self.msg_repo.get(msgidx)
        if not got:
            return
        msg, _body = got

        # Outbound & not yet sent → open editor (Compose dialog)
        if msg.direction == Direction.OUTBOUND and msg.mstate in (
            MessageState.NEW,
            MessageState.DRAFT,
            MessageState.QUEUED,
        ):
            self._open_compose_with_id(msgidx)
            return

        # Inbound or already sent → open read-only Message Form
        payload, transport = self._load_payload_and_transport(msgidx)

        win = MessageFormWindow(
            mode=MessageFormMode.OPEN,
            service=self.message_service,
            system_config=self.system_config,
            config=self.config,
            message_id=msgidx,
            payload=payload,
            transport=transport,
            printable_message=self._printable_message_for_msgidx(msgidx),
            form_registry=self.form_registry,
            parent=self,
        )

        win.deleted.connect(lambda _: self.msgTable.refresh())
        win.replied.connect(self._open_compose_with_id)
        win.replied_all.connect(self._open_compose_with_id)
        win.forwarded.connect(self._open_compose_with_id)

        self._track_message_form(win)
        win.show()


    # ------------------------------------------------------------------
    # 260514, P134
    # Message window form helpers
    # ------------------------------------------------------------------
    def _track_message_form(self, win: QtWidgets.QMainWindow) -> None:
        self._message_forms.append(win)

        def _remove():
            if win in self._message_forms:
                self._message_forms.remove(win)

        win.destroyed.connect(_remove)

    # ------------------------------------------------------------------
    # Payload mapping for View/Compose
    # ------------------------------------------------------------------
    def _load_payload_and_transport(self, msgidx: int) -> Tuple[MessagePayload, Optional[TransportMeta]]:
        """Load a full message record (headers + body) into UI payload."""
        with self.dao._connect() as conn:
            row = conn.execute("SELECT * FROM v_messages_full WHERE msgidx=?", (msgidx,)).fetchone()
            if not row:
                return MessagePayload(subject="(not found)", body=""), None

            payload = MessagePayload(
                bbs_name=row["bbs_call"] or "",
                from_call=row["from_call"] or "",
                to_call=row["to_call"] or "",
                subject=row["subject"] or "",
                body=row["body"] or "",
                type=self._ui_type_from_mtype(row["mtype"]),
                urgent=bool(row["is_urgent"]),
                req_delivery_rcpt=bool(row["is_rdr"]),
                req_read_rcpt=bool(row["is_rrr"]),
                base64_encode=bool(row["is_encoded"]),
            )

            # Transport/display metadata for Message Form OPEN view.
            #
            # Date/time and Local MID are display-only fields:
            # - NEW/DRAFT/QUEUED do not display them.
            # - SENT displays sent_at.
            # - RECEIVED displays sent_at, rcvd_at, and optional Local MID.
            #
            # Prefer recvmsgid for received-message Local MID because inbound local MID
            # assignment stores there; fall back to messageid for older/outbound records.
            keys = row.keys()

            interface_name = row["interface_name"] if "interface_name" in keys else ""
            message_state = row["mstate"] if "mstate" in keys else ""
            sent_at = row["sent_at"] if "sent_at" in keys else ""
            rcvd_at = row["rcvd_at"] if "rcvd_at" in keys else ""

            recvmsgid = row["recvmsgid"] if "recvmsgid" in keys else ""
            messageid = row["messageid"] if "messageid" in keys else ""
            local_msg_id = recvmsgid or messageid or ""

            transport = TransportMeta(
                interface_name=interface_name or "",
                message_state=message_state or "",
                sent_at=sent_at or "",
                rcvd_at=rcvd_at or "",
                local_msg_id=local_msg_id,
            )

            return payload, transport

    def _ui_type_from_mtype(self, mtype_value: int) -> str:
        """Map numeric/enum mtype back to UI string."""
        try:
            mt = MessageType(mtype_value)
        except Exception:
            return "private"
        if mt == MessageType.BULLETIN:
            return "bulletin"
        if mt == MessageType.NTS:
            return "nts"
        return "private"

    # ------------------------------------------------------------------
    # Menu handlers
    # ------------------------------------------------------------------
    def on_import(self) -> None:
        QtWidgets.QMessageBox.information(self, "Import", "Import… (stub)")

    def on_export_all(self) -> None:
        QtWidgets.QMessageBox.information(self, "Export", "Export all… (stub)")

    def on_export_folder(self) -> None:
        QtWidgets.QMessageBox.information(self, "Export", "Export folder… (stub)")

    def on_delete_all(self) -> None:
        QtWidgets.QMessageBox.information(self, "Delete", "Delete all… (stub)")

    def _on_setup_preferences(self) -> None:
        dlg = SetupDialog(
            self.db_path,
            self.config,
            self.system_config,
            self,
        )
        dlg.exec()

        # Preferences dialog has closed; reload active config/settings.
        self.system_config.refresh_from_repos()
        self._on_active_config_changed(self.system_config.get_active_selection())
        self._apply_send_receive_automation_settings()


    def on_new_message(self) -> None:
        """Open Message Form for a brand-new outbound message."""
        win = MessageFormWindow(
            mode=MessageFormMode.NEW,
            service=self.message_service,
            system_config=self.system_config,
            config=self.config,
            parent=self,
        )

        win.saved.connect(lambda mid: self._after_compose_change(mid))
        win.sent.connect(lambda mid: self._after_compose_change(mid))
        win.deleted.connect(lambda mid: self._after_compose_deleted(mid))

        self._track_message_form(win)
        win.show()


    def _open_compose_with_id(self, msgidx: int) -> None:
        """Open Message Form to edit an existing outbound draft/queued message."""
        payload, transport = self._load_payload_and_transport(msgidx)

        win = MessageFormWindow(
            mode=MessageFormMode.NEW,
            service=self.message_service,
            system_config=self.system_config,
            config=self.config,
            message_id=msgidx,
            payload=payload,
            transport=transport,
            parent=self,
        )

        win.setWindowTitle("Edit Message")

        win.saved.connect(lambda mid: self._after_compose_change(mid))
        win.sent.connect(lambda mid: self._after_compose_change(mid))
        win.deleted.connect(lambda mid: self._after_compose_deleted(mid))

        self._track_message_form(win)
        win.show()


    def _after_compose_change(self, _mid: int) -> None:
        """After Save/Send: refresh the table (selection re-focus can be added later)."""
        self.msgTable.refresh()

    def _after_compose_deleted(self, _mid: int) -> None:
        """After Delete from the compose dialog: refresh the table."""
        self.msgTable.refresh()


    def _on_messages_moved(self, _msgidxs, _dest_folderidx) -> None:
        """
        Called when messages are moved between folders (via drag-and-drop).

        We refresh the table for the current folder and clear any stale selection
        and preview, since the previously-selected row may no longer exist here.
        """
        self.msgTable.refresh()
        # Clear selection and preview to avoid showing text for a moved message
        self.msgTable.view.clearSelection()
        self.msgTable.preview.clear()


    # ----------------------------------------------------------------
    # #134/260805, Use sanitized environment for Linux/PyInstaller
    # ----------------------------------------------------------------
    def _open_data_directory(self):
        """
        Open the OutpostX data directory using the system file manager.
        """
        # OPTIONAL: guard against self.paths being missing
        if self.paths is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Open Data Directory",
                "The OutpostX data directory is not available.",
            )
            return

        try:
            open_directory(self.paths.data_dir)

        except DesktopOpenError as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Open Data Directory",
                str(exc),
            )


    def _on_notifications(self) -> None:
        """
        Show the modeless Notifications window.
        """
        if self.notification_window is None:
            self.notification_window = NotificationWindow(
                self.notification_service,
                self,
            )

            self.notification_window.destroyed.connect(
                lambda _obj=None: setattr(self, "notification_window", None)
            )

        self.notification_window.show()
        self.notification_window.raise_()
        self.notification_window.activateWindow()


    # ----------------------------------------------------------------
    # #260525, Help > About.
    # #148, Help > About.  Leveages what was done for OptermX
    # ----------------------------------------------------------------
    # def on_help_about(self) -> None:
    #     QtWidgets.QMessageBox.information(self, "About", "OutpostX\n(c) 2026 Jim Oberhofer")
    def on_help_about(self) -> None:
        dlg = AboutDialog(title=self.apptitle, version=self.appversion, parent=self)
        dlg.exec()


    # ------------------------
    # Message Form Helper 
    # ------------------------
    def _track_message_form(self, win: QtWidgets.QMainWindow) -> None:
        """
        Keep non-modal message forms alive until Qt destroys them.

        Without this, Python can garbage-collect the window after the method
        that created it returns.
        """
        self._message_forms.append(win)

        def _remove(_obj=None):
            if win in self._message_forms:
                self._message_forms.remove(win)

        win.destroyed.connect(_remove)


    # ------------------------
    # Printer Menu Handlers
    # ------------------------
    def on_print_preview(self) -> None:
        """Preview the currently highlighted message."""
        msg = self._current_printable_message()
        if msg is None:
            return
        MessagePrintService(self).preview_message(
            msg,
            include_headers=True,
            printer_name=self._selected_printer_name(),
        )


    def on_print(self) -> None:
        """Print the currently highlighted message."""
        msg = self._current_printable_message()
        if msg is None:
            return
        MessagePrintService(self).print_message(
            msg,
            include_headers=True,
            printer_name=self._selected_printer_name(),
        )

    def on_print_no_headers(self) -> None:
        """Print the currently highlighted message without message headers."""
        msg = self._current_printable_message()
        if msg is None:
            return
        MessagePrintService(self).print_message(
            msg,
            include_headers=False,
            printer_name=self._selected_printer_name(),
        )


    def _current_printable_message(self) -> PrintableMessage | None:
        msgidx = self._current_selected_msgidx()
        if msgidx is None:
            QtWidgets.QMessageBox.information(
                self,
                "Print Message",
                "Select a message to print.",
            )
            return None

        msg = self._printable_message_for_msgidx(msgidx)
        if msg is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Print Message",
                f"Message {msgidx} was not found.",
            )
            return None

        return msg

    def _current_selected_msgidx(self) -> int | None:
        """
        Return msgidx for the current highlighted message row.
        """
        view = getattr(self.msgTable, "view", None)
        model = getattr(self.msgTable, "model", None)
        if view is None or model is None:
            return None

        sel_model = view.selectionModel()
        if sel_model is None:
            return None

        indexes = sel_model.selectedRows()
        if not indexes:
            cur = view.currentIndex()
            if cur.isValid():
                indexes = [cur]

        if not indexes:
            return None

        row = indexes[0].row()

        item_at = getattr(model, "item_at", None)
        if callable(item_at):
            item = item_at(row)
            msg = getattr(item, "msg", None) if item else None
            mid = getattr(msg, "msgidx", None) if msg else None
            if mid is not None:
                return int(mid)

        mid = model.data(model.index(row, 0), QtCore.Qt.ItemDataRole.UserRole)
        return int(mid) if mid is not None else None


    def _printable_message_for_msgidx(self, msgidx: int) -> PrintableMessage | None:
        title_call = ""
        try:
            title_call = self.system_config.get_default_from_call()
        except Exception:
            title_call = ""

        with self.dao._connect() as conn:
            row = conn.execute(
                "SELECT * FROM v_messages_full WHERE msgidx=?",
                (int(msgidx),),
            ).fetchone()

        if not row:
            return None

        return PrintableMessage(
            title_call=title_call,
            from_call=row["from_call"] or "",
            to_call=row["to_call"] or "",
            sent_at=row["sent_at"] or row["rcvd_at"] or "",
            subject=row["subject"] or "",
            local_msg_id=(row["recvmsgid"] or row["messageid"] or ""),
            body=row["body"] or "",
        )

    def _update_print_tooltip(self) -> None:
        """
        Retrieve the name of the default printer for the Printer Tool Tip
        """
        printer = QPrinterInfo.defaultPrinter()
        if printer and not printer.isNull():
            name = printer.printerName()
        else:
            name = "Default Printer"

        self.action_print.setToolTip(f"Print to: {name}")


    def _selected_printer_name(self) -> str:
        return (self.config.get("Printing/defaultPrinter", "") or "").strip()

    def _set_selected_printer_name(self, name: str) -> None:
        self.config.set("Printing/defaultPrinter", (name or "").strip())
        self._update_print_tooltip()

    def _resolved_printer_name_for_display(self) -> str:
        saved = self._selected_printer_name()
        if saved:
            return saved

        info = QPrinterInfo.defaultPrinter()
        if info and not info.isNull():
            return info.printerName()

        return "System default printer"

    def _update_print_tooltip(self) -> None:
        name = self._resolved_printer_name_for_display()

        # Adjust these names to match your toolbar QAction name.
        if hasattr(self, "print"):
            self.action_print.setToolTip(f"Print selected message\nPrinter: {name}")

        if hasattr(self, "action_print"):
            self.action_print.setToolTip(f"Print selected message\nPrinter: {name}")

    def on_print_setup(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)

        saved_name = self._selected_printer_name()
        if saved_name:
            printer.setPrinterName(saved_name)

        dlg = QPageSetupDialog(printer, self)
        dlg.setWindowTitle("Print Setup")

        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        selected_name = printer.printerName()
        if selected_name:
            self._set_selected_printer_name(selected_name)


    # ------------------------------------------------------------------
    # send/receive launcher handlers
    # ------------------------------------------------------------------
    def _on_send_receive(self) -> None:
        self._start_send_receive_session(manual=True)


    def _start_send_receive_session(self, manual: bool = True) -> None:
        """
        Start one Send/Receive session.

        Used by:
        - manual toolbar/menu action
        """
        from dialogs.send_receive_session_dialog import SendReceiveSessionDialog
        from services.send_receive_session import SendReceiveSession

        if self._in_session:
            return

        self._in_session = True
        self.action_send_receive.setEnabled(False)

        def make_session(*, logger, transcript, stop_requested, messages_received=None):
            return SendReceiveSession(
                system_config=self.system_config,
                message_repo=self.msg_repo,
                message_service=self.message_service,
                form_registry=self.form_registry,
                logger=logger,
                transcript=transcript,
                stop_requested=stop_requested,
                messages_received=messages_received,
            )

        # #152/260812: Build Send/Receive session header values
        sel = self.system_config.get_active_selection()

        station_label = (
            (sel.tactical_call or "").strip()
            or (sel.legal_call or "").strip()
        )

        bbs_label = (sel.bbs_name or "").strip()
        interface_label = (sel.interface_name or "").strip()

        dlg = SendReceiveSessionDialog(
            session_factory=make_session,
            station_label=station_label,
            bbs_label=bbs_label,
            interface_label=interface_label,
            config=self.config,
            data_dir=self.db_path.parent,
            parent=self,
        )
        
        dlg.messagesReceived.connect(self._on_messages_received_notification)
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        # force NON-MODAL top-level window
        dlg.setWindowFlags(QtCore.Qt.Window)
        dlg.setModal(False)
        dlg.setWindowModality(QtCore.Qt.NonModal)

        self._sendrecv_dialog = dlg

        def _finished(_ok=None):
            self._in_session = False
            self._sendrecv_dialog = None
            self.action_send_receive.setEnabled(True)
            self.msgTable.refresh()
            self._record_active_config_mru()                # record the most recently used
            self._apply_send_receive_automation_settings()

            if _ok is False:
                self.notification_service.error("Send/Receive failed. Check the session log for details.")
                self._on_notifications()


        dlg.finished.connect(_finished)

        dlg.show()


    def _on_auto_send_receive_timer(self) -> None:
        """
        Timer callback for automatic Send/Receive.

        This fires when:
        - interval timer expires
        - (optionally later) countdown reaches zero

        It simply attempts to start a session.
        """
        if self._in_session:
            return

        self._start_send_receive_session(manual=False)


    def _apply_send_receive_automation_settings(self) -> None:
        """
        Apply Send/Receive automation settings.

        Manual:
        - stop interval timer
        - reset countdown display

        Interval:
        - start timer for configured interval
        - valid range: 1..999 minutes
        """
        try:
            sr = self.system_config.get_send_receive_settings()
        except Exception as exc:
            print(f"WARNING: could not load Send/Receive settings: {exc}")
            sr = None

        mode_obj = getattr(sr, "mode", None)
        mode = getattr(mode_obj, "value", mode_obj)
        mode = (str(mode or "")).strip().lower()
 
        interval_minutes = int(getattr(sr, "interval_minutes", 0) or 0)
        is_interval = mode == "every_n_minutes"

        # ----------------------------
        # Manual / disabled (or not Interval)
        # ----------------------------
        if not is_interval:         # this ensures that a blank (if possible) ends up as a manual
            self._countdown_timer.stop()

            self._countdown_seconds_total = 0
            self._countdown_seconds_left = 0
            self._update_countdown_label()
            return

        # ----------------------------
        # Interval mode
        # ----------------------------
        interval_minutes = max(1, min(interval_minutes, 999))
        interval_ms = interval_minutes * 60 * 1000

        self._countdown_timer.stop()

        self._countdown_seconds_total = interval_minutes * 60
        self._countdown_seconds_left = self._countdown_seconds_total
        self._update_countdown_label()

        if not self._in_session:
            self._countdown_timer.start(1000)     # visual countdown or "interval_ms"?


    # ----------------------------
    # Sound Handler
    # ----------------------------
    def _on_messages_received_notification(self, payload: object) -> None:
        """
        Handle Send/Receive notifications on the UI thread.

        #162:
        - Refresh the message list after each successfully received message.
        - Preserve the existing end-of-receive sound notification.
        """
        data = payload if isinstance(payload, dict) else {}

        if data.get("event") == "message_received":
            self.msgTable.refresh()
            return

        if data.get("play_sound"):
            sound_path = (data.get("sound_path") or "").strip()
            self._play_receive_sound(sound_path)

    # def _on_messages_received_notification(self, payload: object) -> None:
    #     data = payload if isinstance(payload, dict) else {}
    #     sound_path = (data.get("sound_path") or "").strip()

    #     self._play_receive_sound(sound_path)


    def _play_receive_sound(self, sound_path: str = "") -> None:
        """
        Play receive-notification sound (UI thread).

        Uses QSoundEffect for low-latency playback.
        Falls back to beep if path is invalid.
        """
        if not sound_path:
            QtWidgets.QApplication.beep()
            return

        try:
            url = QUrl.fromLocalFile(sound_path)

            # Only reload if file changed (avoids latency)
            if self._receive_sound.source() != url:
                self._receive_sound.setSource(url)

            self._receive_sound.play()

        except Exception as e:
            print(f"Sound playback failed: {e}")
            QtWidgets.QApplication.beep()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        self.config.settings.setValue("MainWindow/splitter/h", self.splitMain.saveState())
        self.msgTable.saveGeometryState()
        self.folderTree.saveState()
        self.config.save_window_state(self, "MainWindow")
        super().closeEvent(e)
