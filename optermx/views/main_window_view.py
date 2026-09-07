# optermx.views/main_window_view.py
# 260522: migrate from PyQt5 to PySide6
from PySide6 import QtGui, QtWidgets


class Ui_MainWindow(object):
    """
    Main application window view for OpTermX.

    This module defines the visual layout and QAction construction
    for the terminal emulator UI.  It intentionally contains only
    view/layout responsibilities and minimal signal wiring.

    Behavioral logic, connection handling, and session management
    are implemented in main_optermx.py and supporting services.
    """

    def setupUi(self, MainWindow):
        """
        Construct the main OptermX window UI.

        Creates the central terminal widgets, menu bar, toolbar,
        status bar, and QAction objects used by the application.
        """
        MainWindow.resize(981, 535)
        MainWindow.setFont(self._font(12))

        self._build_central_widget(MainWindow)

        # Menu Bar
        self.menubar = QtWidgets.QMenuBar()
        MainWindow.setMenuBar(self.menubar)

        #  Toolbar
        self.toolBar = QtWidgets.QToolBar()
        MainWindow.addToolBar(self.toolBar)

        # Status Bar
        self.statusbar = QtWidgets.QStatusBar()
        MainWindow.setStatusBar(self.statusbar)

        self._build_actions()       # creates QAction objects
        self._build_menubar()       # creates menus and adds actions
        self._build_toolbar()       # adds toolbar actions/widgets
        self._wire_actions()        # connects generic view-level actions

        self.retranslateUi()


    def _build_central_widget(self, MainWindow) -> None:
        """
        Create the central terminal display and command-entry widgets.
        """
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)

        self.textEditSession = QtWidgets.QTextEdit(self.centralwidget)
        self.textEditSession.setFont(self._font(10, "Courier New"))
        self.verticalLayout.addWidget(self.textEditSession)

        self.horizontalLayout = QtWidgets.QHBoxLayout()

        self.pushButtonSend = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonSend.setFont(self._font(11))
        self.horizontalLayout.addWidget(self.pushButtonSend)

        self.lineEditCmd = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEditCmd.setFont(self._font(11))
        self.horizontalLayout.addWidget(self.lineEditCmd)

        self.verticalLayout.addLayout(self.horizontalLayout)
        MainWindow.setCentralWidget(self.centralwidget)


    def _build_actions(self) -> None:
        """
        Create QAction objects used by menus and toolbars.
        """
        # File
        self.action_load_cmd_file = QtGui.QAction("Load Command File...", self)
        self.actionE_xit = QtGui.QAction("E&xit", self)
        self.actionE_xit.setShortcut("Esc")

        # Edit
        self.action_cut = QtGui.QAction("Cut", self)
        self.action_cut.setShortcut("Ctrl+X")

        self.action_copy = QtGui.QAction("Copy", self)
        self.action_copy.setShortcut("Shift+Ctrl+C")

        self.action_paste = QtGui.QAction("Paste", self)
        self.action_paste.setShortcut("Ctrl+V")

        self.action_select_all = QtGui.QAction("Select All", self)
        self.action_select_all.setShortcut("Ctrl+A")

        self.action_clear_screen = QtGui.QAction("Clear Screen", self)
        self.action_preferences = QtGui.QAction("Preferences", self)

        # Tools
        self.action_connect = QtGui.QAction("Connect", self)
        self.action_disconnect = QtGui.QAction("Disconnect", self)
        self.actionClose = QtGui.QAction("Close", self)

        self.action_open_data_folder = QtGui.QAction("Open Data Folder", self)

        self.action_hotkey_profiles = QtGui.QAction("Hot Key Profiles...", self)    #260701

        self.action_serial_to_cmd_mode = QtGui.QAction("Serial Cmd Mode", self)
        self.action_serial_to_cmd_mode.setStatusTip("Return to Command Mode from Unproto Mode")
        self.action_serial_to_cmd_mode.setShortcut("Ctrl+M")

        self.action_kpc3_kiss_off = QtGui.QAction("Kantronics KPC", self)
        self.action_aea_kiss_off = QtGui.QAction("AEA TNCs", self)
        self.action_pac_comm_kiss_off = QtGui.QAction("PacComm TNCs", self)

        self.action_color_theme = QtGui.QAction("Color Theme", self)
        self.action_color_theme.setShortcut("Ctrl+T")

        self.action_font = QtGui.QAction("Font", self)
        self.action_increase_font_size = QtGui.QAction("Increase Font Size", self)
        self.action_decrease_font_size = QtGui.QAction("Decrease Font Size", self)

        # Help
        self.action_about = QtGui.QAction("About", self)

        # 260829, #173
        # Terminal input mode
        self.action_character_mode = QtGui.QAction("Character Mode", self)
        self.action_character_mode.setShortcut("Ctrl+H")
        self.action_character_mode.setCheckable(True)
        self.action_character_mode.setStatusTip(
            "Send each typed character immediately without CR/LF"
        )

        # Future/test
        self.actionSend_Test_String = QtGui.QAction("Send Test String", self)


    def _build_menubar(self) -> None:
        """
        Construct the application menu bar and attach actions.
        """
        self.menuFile = self.menubar.addMenu("&File")
        self.menuEdit = self.menubar.addMenu("Edit")
        self.menuTools = self.menubar.addMenu("Tools")
        self.menuHelp = self.menubar.addMenu("Help")

        self.menuKISS_Off = self.menuTools.addMenu("KISS Off...")

        self.menuFile.addAction(self.action_load_cmd_file)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionE_xit)
        self.menuFile.addSeparator()

        self.menuEdit.addAction(self.action_cut)
        self.menuEdit.addAction(self.action_copy)
        self.menuEdit.addAction(self.action_paste)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.action_select_all)
        self.menuEdit.addAction(self.action_clear_screen)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.action_preferences)

        self.menuTools.addAction(self.action_connect)
        self.menuTools.addAction(self.action_disconnect)
        self.menuTools.addSeparator()
        self.menuTools.addAction(self.action_character_mode)
        self.menuTools.addSeparator()
        self.menuTools.addAction(self.action_open_data_folder)
        self.menuTools.addAction(self.action_hotkey_profiles)

        self.menuTools.addSeparator()
        self.menuTools.addAction(self.action_serial_to_cmd_mode)

        self.menuKISS_Off.addAction(self.action_kpc3_kiss_off)
        self.menuKISS_Off.addAction(self.action_aea_kiss_off)
        self.menuKISS_Off.addAction(self.action_pac_comm_kiss_off)
        self.menuTools.addAction(self.menuKISS_Off.menuAction())

        self.menuTools.addSeparator()
        self.menuTools.addAction(self.action_color_theme)
        self.menuTools.addAction(self.action_font)
        self.menuTools.addAction(self.action_increase_font_size)
        self.menuTools.addAction(self.action_decrease_font_size)

        self.menuHelp.addAction(self.action_about)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuTools.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())


    def _build_toolbar(self) -> None:
        """
        Populate the main toolbar with commonly used actions/widgets.
        """
        self.toolBar.setWindowTitle("toolBar")
        self.toolBar.addAction(self.action_connect)
        self.toolBar.addAction(self.action_disconnect)


    def _wire_actions(self) -> None:
        """
        Connect generic view-level actions to UI widgets.

        Application-specific behavior is connected in main_optermx.py.
        """
        self.action_cut.triggered.connect(self.textEditSession.cut)
        self.action_copy.triggered.connect(self.textEditSession.copy)
        self.action_paste.triggered.connect(self.textEditSession.paste)
        self.action_select_all.triggered.connect(self.textEditSession.selectAll)
        self.action_clear_screen.triggered.connect(self.textEditSession.clear)

    def retranslateUi(self):
        """
        Apply user-visible text strings to the UI.

        Retained for compatibility with Qt translation workflows,
        although OpTermX currently uses only English text.
        """
        self.setWindowTitle("Optermx")
        self.pushButtonSend.setText("Send")
        self.lineEditCmd.setPlaceholderText("Command <enter>")

    # ------------------------------------------------------------------
    # Font Helper
    # ------------------------------------------------------------------
    def _font(self, point_size: int, family: str | None = None) -> QtGui.QFont:
        """
        Convenience helper for constructing QFont objects.
        """
        font = QtGui.QFont()
        if family:
            font.setFamily(family)
        font.setPointSize(point_size)
        return font


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
