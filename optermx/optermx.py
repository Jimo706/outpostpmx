"""
08/21/25: first implementation.  Gui sort of works.
08/22/25: Add Preferences Form and supporting code 
08/24/25: Add Code to load ConnIF combo box, add Handler for IF change
"""
import sys                                  # need for sys.exit()
import time
import warnings                             # need to turn off DeprecationWarning msgs
import platform

from pathlib import Path
from datetime import datetime

# 260522: Migrate from PyQt5 to PySide6
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QComboBox,
    QPushButton,
    QWidget,
    QSizePolicy,
    QFontDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QSignalBlocker, Slot
from PySide6.QtGui import QFont, QTextCursor, QIcon, QAction
from PySide6.QtWidgets import QFileDialog

from config.appconfig import appconfig             # needed to get the connection configs
from config.most_recent_config import MostRecentConfig
from dialogs.about_dialog import AboutDialog
from dialogs.hotkey_profile_dialog import HotkeyProfileDialog

from services.gui_adapter import GUIAdapter
from services.app_paths import AppPaths
from services.app_info import AppInfo
from services.desktop_services import (
    DesktopOpenError,
    open_directory,
)
from services.hotkey_profile_service import HotkeyProfileService
from transports.connection_factory import get_connection
from transports.exceptions import OpTermxError
from widgets.command_entry_edit import CommandEntryEdit
from pref_dialog import PrefDialog          # required for the Preference Dialog
from utils import to_bool

from views.main_window_view import Ui_MainWindow

# temporarily suppress the Deprecation Warning using Python's warnings module
warnings.filterwarnings("ignore", category=DeprecationWarning)

""" 
  Keep everything internal lowercase and uniform, and only "pretty-print"  show it in the UI or logs
  Keys = canonical internal values (always lowercase)
  Values = presentation strings
""" 
IF_PRESENTATION = {
    "serial": "Serial",
    "telnet": "Telnet",
    "tcp": "Telnet",
    "agwpe-bbs": "Agwpe-BBS",
    "agwpe-unproto": "Agwpe-Unproto",
    "ssh": "SSH",
    "test": "Test",
}

class Window(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()                      # initializes the parent class Ui_MainWindow
        self.setupUi(self)                      # runs the setupUi function in Ui_MainWindow

        # 260522: Replace generated QLineEdit command box with custom multiline command-entry widget.
        old_cmd = self.lineEditCmd

        self.lineEditCmd = CommandEntryEdit(self.centralwidget)
        self.lineEditCmd.setFont(old_cmd.font())
        self.lineEditCmd.setObjectName("lineEditCmd")

        # Replace the old widget in the existing Send row layout.
        idx = self.horizontalLayout.indexOf(old_cmd)
        if idx >= 0:
            self.horizontalLayout.removeWidget(old_cmd)
            old_cmd.deleteLater()
            self.horizontalLayout.insertWidget(idx, self.lineEditCmd)


        self.lineEditCmd.setFocus()             # set the cursor in the command line
        self.textEditSession.setReadOnly(True)
        self.selected_conn_if = None            # define the variable for the selected IF, set as lower case
        self.is_connected = None
        self.is_dark_mode = False               # 250826: # flag to keep track of the color scheme state

        self.paths = AppPaths(app_name=AppInfo.APP_NAME)        # 260702
        self.ini = appconfig(config_dir=self.paths.optermx_dir) # 260702

        self.paths = AppPaths(app_name=AppInfo.APP_NAME)           # 260526: must come before self.log_file =...
        self.hotkeys = HotkeyProfileService(self.paths.hotkey_profiles_file)

        self.apptitle = AppInfo.TITLE
        self.appversion = AppInfo.APP_VERSION
        self.setWindowTitle(f"{self.apptitle}    v{self.appversion}")
        self.setWindowIcon(QIcon(self.paths.app_icon()))
        self.apply_native_style()

        self.cfg = None
        self.log_file = self._open_session_log()            # 260525
        self.mrc = MostRecentConfig(
            file_menu=self.menuFile,                       # your File menu (QMenu)
            # storage_path="~/.OpTermx/mrc.json",            # puts this under the <user> directory 
            storage_path=str(self.paths.mrc_file),
            ini=self.ini,
            parent=self
        )

        self.restore_window_geometry()                      # Restore the form geometries

        # Set up the adapter and links to gui controls
        self.adapter = GUIAdapter(parent=self, local_echo=False)
        self.adapter.message_ready.connect(self.on_message_ready) 
      
        # state changes that should flip buttons, icons, labels, etc.
        self.adapter.connectedChanged.connect(self.on_connected_changed)

        # Connect (signal) to send Cmd data to the (slot) Session process 
        self.lineEditCmd.sendRequested.connect(self.click_handler_cmd_send)
        self.lineEditCmd.controlCharRequested.connect(self.send_control_char)   
        self.lineEditCmd.functionKeyRequested.connect(self.insert_hotkey_text)  # 260701             

        # 260829: #173 Character Mode
        self.lineEditCmd.characterRequested.connect(self.send_character)
        self.action_character_mode.toggled.connect(self.set_character_mode)

        self.pushButtonSend.clicked.connect(self.click_handler_cmd_send)       # the push button
        self.actionE_xit.triggered.connect(self.close)                      # Connect File > Exitto close form.
        self.action_connect.triggered.connect(self.click_connect)           # Connect Tools > Connect 
        self.action_disconnect.triggered.connect(self.click_disconnect)      # 250826: Connect Tools > Disconnect 
        self.action_open_data_folder.triggered.connect(self.open_data_folder)  # 260526: Connect Tools > open file manager
        self.action_hotkey_profiles.triggered.connect(self.show_hotkey_profiles) # 260701
        self.action_preferences.triggered.connect(self.show_preferences)    # 250822: Connect Edit > Preferences
        self.action_increase_font_size.triggered.connect(self.increase_font_size) # 250824: ConnectTool Bar a | A to Menu
        self.action_decrease_font_size.triggered.connect(self.decrease_font_size) # 250824: ConnectTool Bar a | A to Menu
        self.action_font.triggered.connect(self._open_font_dialog)           # 250824: Connect Tools > Font menu
        self.action_color_theme.triggered.connect(self.toggle_colors)       # 250826: Connect button click to the toggle function
        self.action_kpc3_kiss_off.triggered.connect(self.kpc3_kiss_off)     # 251003: Connect Tools > Kiss Off > KPC3Comm
        self.action_aea_kiss_off.triggered.connect(self.aea_kiss_off)       # 251003: Connect Tools > Kiss Off > AEA
        self.action_pac_comm_kiss_off.triggered.connect(self.kpc3_kiss_off) # 251003: Connect Tools > Kiss Off > PacComm
        self.action_serial_to_cmd_mode.triggered.connect(self.serial_to_cmd_mode)        # 251005: send Ctrl-C to serial port
        self.action_load_cmd_file.triggered.connect(self.load_cmd_file)     # 260524: File > Load Cmd File
        self.action_about.triggered.connect(self.show_about)                # 260525: Help > About


        # 250824: ADD the combo box to the tool bar.  This cannot be added by Qt Designer
        self.cboConnIF = QComboBox(self)
        self.cboConnIF.addItem("Serial")
        self.cboConnIF.addItem("Telnet")
        self.cboConnIF.addItem("Agwpe-BBS")
        self.cboConnIF.addItem("Agwpe-Unproto")
        # self.cboConnIF.addItem("SSH")
        # self.cboConnIF.addItem("TEST")            # used for debugging flows between classes

        lastIf = self.ini.get('general', 'interface')        # 250908: get the last IF
        self.cboConnIF.setCurrentText(lastIf)       # set to cbo display to the lastIf used
        self.on_ConnIF_changed(1)                   # 'click' the combo box to load the last setting

        self.cboConnIF.currentIndexChanged.connect(self.on_ConnIF_changed)

        # insert the cbo ahead of the self.action_connect button
        self.toolBar.insertWidget(self.action_connect, self.cboConnIF)

        #350824: add font size + and - buttons on Tool Bar
        spacer = QWidget()                                                  # First, add an expading spacer widget
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolBar.addWidget(spacer)
        
        button_decrease_size = QAction("A", self)                           # Add the first right-justified actions
        font = QFont("Arial", 9)                                            # Set font to "Arial", size is 10 points
        button_decrease_size.setFont(font)
        button_decrease_size.setToolTip('Decrease the display font size')
        button_decrease_size.triggered.connect(self.decrease_font_size)
        self.toolBar.addAction(button_decrease_size)

        button_increase_size = QAction("A", self)                           # Add the seond right-justified actions
        font = QFont("Arial", 14)                                           # Set font to "Arial" size is 16 points
        button_increase_size.setFont(font)
        button_increase_size.setToolTip('Increase the display font size')
        button_increase_size.triggered.connect(self.increase_font_size)
        self.toolBar.addAction(button_increase_size)

        # Initialize display colors to the default (black on white)
        self.set_light_mode()
        self.action_disconnect.setEnabled(False)

    def apply_native_style(self) -> None:
        """
        Apply a platform-appropriate Qt widget style.

        Notes:
        - Windows: prefer "windowsvista" for a more native look.
        - macOS: do not override; Qt's native macOS style is typically best.
        - Linux: use "fusion" for consistency across distros/themes.
        """
        osname = platform.system()

        if osname == "Windows":
            QtWidgets.QApplication.setStyle("windowsvista")
        elif osname == "Darwin":
            # macOS: let Qt use the built-in macOS style
            pass
        elif osname == "Linux":
            QtWidgets.QApplication.setStyle("fusion")



   # ----------------------------------------------
   #  Code Section for handlers for all form UI clicks
   # ----------------------------------------------
    def keyPressEvent(self, event):
        """ Detect the ESC button, then exit the program"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()                                  # closes a specific window
            sys.exit()                                    # terminates the entire program.
        else:
            super().keyPressEvent(event)                  # For other keys, call the base class implementation


    # 250824, CLICK HANDLER for a change in the Interface choice.  Save it to the global variable
    def on_ConnIF_changed(self, index):
        # #173: Character Mode is Serial-only.
        # Changing interfaces always returns to normal Line Mode.
        if (
            self.action_character_mode.isChecked()
            and self.cboConnIF.currentText().lower() != "serial"
        ):
            self.action_character_mode.setChecked(False)

        self.selected_conn_if = self.cboConnIF.currentText().lower()  # 251003, keep canonical internal values as lowercase
        self.load_config(self.selected_conn_if)      
        self.textEditSession.insertPlainText(f"ConnIF selection to {self.selected_conn_if}\n")   # writes IF to the UI
        self.update_status(self.selected_conn_if)

        self.ini.set('general', 'interface', self.selected_conn_if)
        self.ini.save()             # 250908: Save the Selected IF just chosen


    # 250822, CLICK HANDLER for opening the Preferences menu
    def show_preferences(self):
            # DEBUG: import inspect
            # DEBUG: print("PrefDialog class loaded from:", inspect.getfile(PrefDialog))

            dlg = PrefDialog(ini=self.ini, parent=self)
            dlg.exec()
            # DEBUG: comment out the previous lone and comment back in these lines if there are problems.
            # if dlg.exec():      # OK pressed, dialog writes .ini directly
            #     print("OK, .ini updated")
            # else:               # Cancel pressed dialog writes .ini directly
            #     print("Cancel, no .ini update")


    #250821, CLICK HANDLER for when the user enters a command and presses CR or Send
    #260522, Updated
    def click_handler_cmd_send(self, text=None):
        """
        Send command-entry text to the active connector.

        Called by:
        - CommandEntryEdit.sendRequested(str) when Enter is pressed
        - Send button clicked, with no text argument

          Action	                    Result
          ----------------------------  ------------------------------------------------
          Type command + Enter	        Sends command plus final CR
          Click Send	                Sends contents of box
          Paste multiple lines + Enter	Sends all pasted lines, preserving line breaks
          Shift+Enter	                Inserts a newline instead of sending
        """
        if not self.adapter.is_connected:
            return

        # If called by the Send button, pull current text from the command-entry widget.
        if text is None or isinstance(text, bool):
            text = self.lineEditCmd.toPlainText()

        if text is None:
            return

        # Preserve pasted multi-line text. Add a final CR if the user did not include one.
        outbound = self._normalize_outbound_text(text)

        if outbound == "":
            return

        # Local echo for socket-like text modes.
        if self.selected_conn_if.lower() in ("telnet", "agwpe-bbs", "agwpe-unproto"):
            self.textEditSession.insertPlainText(outbound)

        self.adapter.send_to_connector(outbound)

        self.lineEditCmd.clear()
        self.lineEditCmd.setFocus()


    def send_control_char(self, data: bytes):
        """
        Send raw Ctrl-<key> byte from CommandEntryEdit to the active connector.
        Example: Ctrl-C -> b'\\x03', Ctrl-D -> 0x04, Ctrl-Z -> 0x1A
        """
        if not self.adapter.is_connected:
            return

        if not data:
            return

        self.adapter.send_to_connector(data)
        self.lineEditCmd.setFocus()


    def _normalize_outbound_text(self, text: str) -> str:
        """
        Normalize command-entry text for terminal sending.

        QPlainTextEdit stores line breaks as \\n.
        Most packet/TNC/Telnet command paths expect CR.
        """
        outbound = str(text).replace("\r\n", "\n").replace("\r", "\n")
        outbound = outbound.replace("\n", "\r")

        if not outbound.endswith("\r"):
            outbound += "\r"

        return outbound


    def load_config(self, iftype):
        """ 
        Loads the config params for all subsequent connects and status. Called by on_ConnIF_changed. 
        """
        # DEBUG: print(f"!! MAIN > load_config > iftype: {iftype}")
        if iftype == "serial":
            self.cfg = self.ini.getSerial()

        elif iftype in ("tcp", "telnet"):   
            self.cfg = None
            self.cfg = self.ini.getTelnet()
            # DEBUG: print(f"!! MAIN > load_config > cfg: {self.cfg}")

        elif iftype in ("agwpe-bbs"):    
            self.cfg = self.ini.getAgwpe()

        elif iftype in ("agwpe-unproto"):    
            self.cfg = self.ini.getAgwpe()
        else:
            print(f"update_status, iftype not found {iftype}")


    def update_status(self, iftype):
        """ 
        Called From MRC or on_ConnIF_changed (cbo) to select the correct cbo entry 
           and write the status line
        """
        # for an interface change by MRC or cbo, set the correct cbo entry
        # map the iftype to the cbo index
        ifmap = {"serial": 0, "telnet": 1, "tcp": 1, "agwpe-bbs": 2, "agwpe-unproto": 3, "ssh": 4}

        key = (iftype or "")
        idx = ifmap.get(key)
        if idx is not None:
            self.cboConnIF.setCurrentIndex(idx)
        else:
            # Unknown type: pick a safe default and bail early
            self.cboConnIF.setCurrentIndex(0)
            print(f"update_status: unknown interface Type: {iftype!r}")
            return

        # get the current defined IF config and define the cfg portion of the status line
        status = ""
        # DEBUG: print(f"!! MAIN > update_status > iftype: {iftype}")
        if iftype == "serial":
            status = f'{self.cfg["port"]} {self.cfg["baudrate"]},{self.cfg["databits"]},{self.cfg["parity"][0]},{self.cfg["stopbits"]}'

        elif iftype in ("tcp", "telnet"):    
            status = f'{self.cfg["host"]}:{self.cfg["port"]}'

        elif iftype in ("agwpe-bbs"):    
            status = f'{self.cfg["host"]}:{self.cfg["port"]}, BBS={self.cfg["tocall"]}'

        elif iftype in ("agwpe-unproto"):    
            status = f'{self.cfg["host"]}:{self.cfg["port"]}, ID={self.cfg["unprotoid"]}'
        else:
            print(f"update_status, iftype not found {iftype}")

        # get the presentation verion of iftype and write the status line
        self.statusbar.showMessage(f"{IF_PRESENTATION.get(iftype, iftype)} - {status}")

        return


    def validate_config(self, iftype: str, cfg: dict[str, any]) -> bool:
        """ #251003, Config validation before actual connect """
        REQUIRED = {
            "serial":       ["port", "baudrate"],
            "telnet":       ["host", "port"],
            "ssh":          ["host", "username"],
            "agwpe-bbs":    ["host", "port", "fmcall", "tocall"],
            "agwpe-unproto":["host", "port", "fmcall", "unprotoid"],
        }

        def _is_missing(v: any) -> bool:
            return v is None or (isinstance(v, str) and v.strip() == "")

        iftype = (iftype or "").lower()
        req = REQUIRED.get(iftype)
        if not req:
            QMessageBox.warning(None, "Warning", f"Unknown interface type: {iftype}")
            return False

        # gather missing required fields
        missing: List[str] = [k for k in req if _is_missing(cfg.get(k))]

        if missing:
            msg = "Missing or empty fields:\n  - " + "\n  - ".join(missing)
            QMessageBox.warning(None, "Configuration", msg)
            return False

        return True


    # ----------------------------------------------------------------
    # 251005: Manage form geometries  
    # ----------------------------------------------------------------
    def closeEvent(self, event):
        # save window position and size
        self.ini.set('window', 'geometry', self.saveGeometry().toBase64().data().decode('ascii'))
        self.ini.save()   # if your appconfig writes to disk
        super().closeEvent(event)
    
    def restore_window_geometry(self):
        geom_b64 = self.ini.get('window', 'geometry', fallback=None)
        if geom_b64:
            self.restoreGeometry(QByteArray.fromBase64(geom_b64.encode('ascii')))


    # ----------------------------------------------------------------
    # 251005: Control Commands for different modes 
    # ----------------------------------------------------------------
    def serial_to_cmd_mode(self):
        """ Send Ctrl-C to serial port to move from Unproto Mode to Command Mode """
        if self.selected_conn_if == "serial":
            if self.adapter.is_connected:
                byte_string = b'\x03'       # send Ctrl-C '0x03' (ETX) over the serial link
                self.adapter.send_to_connector(byte_string)


    # ----------------------------------------------------------------
    # 251003: KISS OFF functions, only if Serial is selected and Connected
    # ----------------------------------------------------------------
    def kpc3_kiss_off(self):
        """ Force Kantronics nad PacComm TNC in KISS or Host mode back into Command Mode """
        if self.selected_conn_if == "serial":
            # Kantronics, PacComm Kiss Off  192 255 192
            byte_string = b'\xc0\xff\xc0'
            self.adapter.send_to_connector(byte_string)
    
    def aea_kiss_off(self):
        """ Force an AEA TNC in KISS or Host mode back into Command Mode """
        if self.selected_conn_if == "serial":
            # AEA Kiss Off, Host Off, CR CR CR
            byte_string = b'\r\r\r'
            self.adapter.send_to_connector(byte_string)
        

    # ----------------------------------------------------------------
    # 250823: FONT CLICK HANDLER methods to increase and decrease font size
    # ----------------------------------------------------------------
    def increase_font_size(self):
        current_font = self.textEditSession.font()
        new_size = current_font.pointSize() + 1             # Increase by 2 points
        new_font = QtGui.QFont(current_font.family(), new_size)
        self.textEditSession.setFont(new_font)              # set the session font size
        self.lineEditCmd.setFont(new_font)                  # set the command window font size

    def decrease_font_size(self):
        current_font = self.textEditSession.font()
        new_size = current_font.pointSize() - 1             # Decrease by 2 points
        if new_size > 0: # Prevent font size from becoming zero or negative
            new_font = QtGui.QFont(current_font.family(), new_size)
            self.textEditSession.setFont(new_font)          # set the session font size
            self.lineEditCmd.setFont(new_font)              # set the command window font size

    def _open_font_dialog(self):
        # Open the font dialog with the current font of the label as initial selection
        font, ok = QFontDialog.getFont(self.textEditSession.font(), self)
        if ok:
            self.textEditSession.setFont(font)
            # print("Selected Font:", font.toString())

    # ----------------------------------------------------------------
    # 250823: Background TOGGLE CLICK HANDLER methods 
    # ----------------------------------------------------------------
    def set_light_mode(self):
        """Sets the QLineEdit to black text on a white background."""
        self.textEditSession.setStyleSheet("color: black; background-color: white;")
        self.is_dark_mode = False

    def set_dark_mode(self):
        """Sets the QLineEdit to white text on a black background."""
        self.textEditSession.setStyleSheet("color: white; background-color: black;")
        self.is_dark_mode = True

    def toggle_colors(self):
        """Toggles between the light and dark color schemes."""
        if self.is_dark_mode:
            self.set_light_mode()
        else:
            self.set_dark_mode()


    # ----------------------------------------------------------------
    # #260525, Logging Helper.
    # ----------------------------------------------------------------

    def _open_session_log(self) -> Path:
        """
        Create today's log file if needed and append a session-start banner.
        """
        # logs_dir = self._get_data_dir() / "logs"
        logs_dir = self.paths.logs_dir
        logs_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        log_path = logs_dir / f"optermx{now:%y%m%d}.log"

        banner = (
            "\n"
            "---------------------------------------------------\n"
            f"{now:%d-%b %H:%M:%S}: {self.apptitle} v{self.appversion}\n"
            "---------------------------------------------------\n"
        )

        with open(log_path, "a", encoding="ascii", errors="replace") as f:
            f.write(banner)

        return log_path


    def _write_session_log(self, text: str) -> None:
        """
        Append display text to today's session log.
        """
        if not text:
            return

        try:
            with open(self.log_file, "a", encoding="ascii", errors="replace") as f:
                f.write(str(text))
        except Exception:
            # Logging must never break terminal operation.
            pass


    # ----------------------------------------------------------------
    # #260525, Help > About.
    # ----------------------------------------------------------------
    def show_about(self):
        dlg = AboutDialog(title=self.apptitle, version=self.appversion, parent=self)
        dlg.exec()

    # ----------------------------------------------------------------
    # #260524, Send a file Helper.
    # ----------------------------------------------------------------
    def load_cmd_file(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Command File",
            "",
            "Text files (*.txt *.cmd *.scr);;All files (*.*)"
        )

        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()

        except Exception as e:
            QMessageBox.warning(self, "Open Command File", f"Could not read file:\n{e}")
            return

        self.lineEditCmd.setPlainText(text)
        self.lineEditCmd.setFocus()


 # ----------------------------------------------------------------
# #260526, Open System File Manager helper
# #134/260805, Use sanitized environment for Linux/PyInstaller
# ----------------------------------------------------------------
    def open_data_folder(self):
        """
        Open the OpTermX data directory using the system file manager.
        """
        try:
            open_directory(self.paths.data_dir)

        except DesktopOpenError as exc:
            QMessageBox.warning(
                self,
                "Open Data Folder",
                str(exc),
            )

    # ----------------------------------------------------------------
    # #260701, Hot-Key helpers
    # ----------------------------------------------------------------
    def show_hotkey_profiles(self):
        """
        Open the Hot Key Profile dialog.
        """
        dlg = HotkeyProfileDialog(service=self.hotkeys, parent=self)
        dlg.exec()

        # Reload after dialog closes in case profiles changed.
        self.hotkeys.load()

    def insert_hotkey_text(self, key_name: str):
        """
        Insert the active profile's hot key text into the command-entry box.

        The text is not sent automatically. The operator can edit it, then press
        Send or Enter.
        """
        text = self.hotkeys.get_active_key_text(key_name)

        if not text:
            self.statusBar().showMessage(f"{key_name} is not defined for the active Hot Key profile")
            return

        # once a filled-in F-key is sent, clear the previous status message.
        self.statusBar().clearMessage()

        self.lineEditCmd.setPlainText(text)
        self.lineEditCmd.setFocus()


    # ----------------------------------------------------------------
    # #250821, CONNECT CLICK HANDLER for when the user presses Connect.
    # ----------------------------------------------------------------
    #250821, CLICK HANDLER for when the user presses Connect.  The If must be selected and configured
    def click_connect(self):
        # DEBUG: print(f"!! MAIN > click_connect > iftype: {self.selected_conn_if}")

        # load the config based on the connection type and validate that all required fields are filled in
        self.load_config(self.selected_conn_if)     
        result = self.validate_config(self.selected_conn_if, self.cfg)
        if not result:
            return

        self._write_session_log("-- CONNECT --\n")
        self.on_connected_changed(True)                                 # toggle the Connect/Disconnect button

        match self.selected_conn_if:                                    # matches what is listed in cboConnIF, lower case
            case "serial":
                self.adapter.run_serial(self.mrc, self.cfg)

            case "telnet":
                self.adapter.run_telnet(self.mrc, self.cfg)

            case "agwpe-bbs":
                self.adapter.run_agwpe_connect(self.mrc, self.cfg)        # common Telnet Connect, register, connect to a BBS
                self.adapter.run_agwpe_bbs(self.mrc, self.cfg)            # BBS-specific connect functions

            case "agwpe-unproto":
                self.adapter.run_agwpe_connect(self.mrc, self.cfg)        # common Telnet Connect, register
                self.adapter.run_agwpe_unproto(self.mrc, self.cfg)        # set up unproto

            case "ssh":
                self.adapter.run_ssh()

            case "test":
                self.display_to_session(">>>MAIN > TEST > was pressed\n")
                print(f">>>MAIN > TEST > was pressed")
                self.adapter.run_test()            # Telnet Connect, register, connect to a BBS


    #250821, CLICK HANDLER for when the user presses Connect.  The If must be selected and configured
    def click_disconnect(self):
        if self.adapter.is_connected:
            self.adapter.conn.disconnect()

        self._write_session_log("-- DISCONNECT --\n")
        self.action_connect.setEnabled(True)
        self.action_disconnect.setEnabled(False)
        self.on_connected_changed(False)

    def display_to_session(self, text: str):
        """a local copy of the a-end_to_session call, this works """
        self.textEditSession.moveCursor(QTextCursor.MoveOperation.End)  # move cursor to the end
        self.textEditSession.insertPlainText(text)              # insert raw text without extra formatting
        self.textEditSession.ensureCursorVisible()              # # make sure the last line is visible

        self._write_session_log(text)

    # ----------------------------------------------------------------
    # #173/260829: Character-at-a-time terminal mode
    # ----------------------------------------------------------------
    def set_character_mode(self, enabled: bool):
        """
        Toggle between normal Line Mode and serial Character Mode.

        Line Mode:
            Accumulate text and send it with CR when Enter/Send is pressed.

        Character Mode:
            Send each printable character immediately with no CR/LF.
        """
        # Character Mode only makes sense for the serial TNC interface.
        if enabled and self.selected_conn_if != "serial":
            self.action_character_mode.setChecked(False)

            QMessageBox.information(
                self,
                "Character Mode",
                "Character Mode is available only with the Serial interface."
            )
            return

        self.lineEditCmd.clear()
        self.lineEditCmd.set_character_mode(enabled)

        if enabled:
            self.pushButtonSend.setEnabled(False)
            self.statusBar().showMessage("Serial - Character Mode")
        else:
            self.pushButtonSend.setEnabled(True)
            self.update_status(self.selected_conn_if)

        self.lineEditCmd.setFocus()

    def send_character(self, text: str):
        """
        Send one character exactly as typed, without CR or LF.
        """
        if not self.adapter.is_connected:
            return

        if self.selected_conn_if != "serial":
            return

        if not text:
            return

        self.adapter.send_to_connector(text)
        self.lineEditCmd.setFocus()


    @Slot(str)
    def on_message_ready(self, text: str):
        """
        The slot says "When I get a str, append it to the session view."  This runs on the GUI thread (safe for widget updates).
        Append received text to the session display and session log.
        """
        self.textEditSession.moveCursor(QTextCursor.MoveOperation.End)
        self.textEditSession.insertPlainText(text)
        self.textEditSession.ensureCursorVisible()
        self.textEditSession.viewport().update()

        self._write_session_log(text)                                                                # choose for QTextEdit/QPlainTextEdit:


    @Slot(bool)
    def on_connected_changed(self, connected: bool):
        # print(f"on_connected_changed = {connected}")
        # flip buttons, icons, status bar, etc.
        self.action_connect.setEnabled(not connected)
        self.action_disconnect.setEnabled(connected)
        self.statusBar().showMessage("Connected" if connected else "Disconnected")


app = QApplication([])

# set up application identity before openinig the window.
app.setOrganizationName(AppInfo.ORG_NAME)
app.setApplicationName(AppInfo.APP_NAME)
app.setApplicationVersion(AppInfo.APP_VERSION)

app.setWindowIcon(QIcon(AppPaths.app_icon()))

window = Window()

window.show()
app.exec()

