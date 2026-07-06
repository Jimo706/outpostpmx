"""
In interface_setup_widget.py, the “blob” is created in get_profile(), 
read in set_profile(), converted to a dict in to_dict(), and rehydrated 
in from_dict() — JSON and SQLite happen later, outside the widget.

SQLite (JSON payload)
        ↓
Repository (json.loads)
        ↓
dict
        ↓
from_dict()
        ↓
InterfaceProfile  ←───── set_profile()  ←──── UI
        ↑
get_profile()  ────────→ InterfaceProfile
        ↑
User edits UI

"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

from PySide6 import QtCore, QtGui, QtWidgets

# 251128, ADDED 2 lines
import sys
import glob

#TODO: set Serial Comm Port to show active ports (QSerialPortInfo)


def list_serial_ports() -> list[str]:
    """Return a list of available serial ports for the current OS."""
    ports = []

    if sys.platform.startswith("win"):
        for i in range(1, 33):
            ports.append(f"COM{i}")

    elif sys.platform.startswith("linux"):
        patterns = [
            "/dev/ttyS*",
            "/dev/ttyUSB*",
            "/dev/ttyACM*",
            "/dev/serial/by-id/*",
        ]
        for pat in patterns:
            for port in glob.glob(pat):
                ports.append(port)

    elif sys.platform.startswith("darwin"):
        ports.extend(glob.glob("/dev/tty.*"))
        ports.extend(glob.glob("/dev/cu.*"))

    return sorted(set(ports))


# Toggle thisto hide or disable the non-used Interface types
USE_HIDE_MODE = True

# Standard widths to keep Linux from stretching fields too wide
DEFAULT_INPUT_WIDTH = 300       # typical text field
SMALL_INPUT_WIDTH = 150         # ports, baud, etc.


@dataclass
class InterfaceProfile:
    """
    Simple data container matching the Interface IRS fields.
    Adjust / extend as needed when wiring to the real DB schema.

    IMPORTANT:
    This dataclass defines the SHAPE of the Interface Profile "blob".
    Every field here becomes a key in the JSON payload stored in SQLite.
    """
    interface_name: str = ""
    description: str = ""
    interface_type: str = "TNC_TAPR"  # "TNC_TAPR", "TNC_SCS", "TELNET", "AGWPE"

    # TNC-related
    tnc_com_port: str = ""
    tnc_baud: str = ""
    tnc_data_bits: str = ""
    tnc_parity: str = ""
    tnc_stop_bits: str = ""
    tnc_flow_control: str = ""

    tnc_cmd_prompt: str = ""
    tnc_timeout_prompt: str = ""
    tnc_disconnect_prompt: str = ""

    tnc_mycall_cmd: str = ""
    tnc_connect_cmd: str = ""
    tnc_converse_cmd: str = ""
    tnc_daytime_cmd: str = ""
    tnc_include_cmd_prefix: bool = False
    tnc_cmd_prefix: str = ""

    tnc_send_init_cmds: bool = False
    tnc_init_before: str = ""
    tnc_init_after: str = ""

    # General network
    remote_host: str = ""
    remote_port: str = ""
    remote_timeout: str = ""

    # Telnet
    telnet_logon_prompt: str = ""
    telnet_password_prompt: str = ""

    # AGWPE
    agw_radio_port: str = ""
    agw_tx_buffer_size: str = ""
    agw_logon_required: bool = False
    agw_logon: str = ""
    agw_password: str = ""


class InterfaceSetupWidget(QtWidgets.QWidget):
    """
    Right-side Interface editor widget for the Interface Profiles Manager.

    - Top group: name, description, type
    - TNC group
    - General Network group
    - Telnet group
    - AGWPE group

    Group boxes are enabled/disabled (or shown/hidden) depending on Interface Type.
    """
    changed = QtCore.Signal()  # emitted when any field changes

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self._profile = InterfaceProfile()

        self._build_ui()
        self._connect_signals()
        self._apply_interface_type(self._profile.interface_type)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1) Interface definition
        self.grpInterface = QtWidgets.QGroupBox("Interface Definition", self)
        self.grpInterface.setStyleSheet("QGroupBox { font-weight: bold; }")     # makes label BOLD
        iface_layout = QtWidgets.QFormLayout(self.grpInterface)

        self.edInterfaceName = QtWidgets.QLineEdit(self.grpInterface)
        self.edInterfaceName.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.txtDescription = QtWidgets.QPlainTextEdit(self.grpInterface)
        self.txtDescription.setFixedHeight(60)  # or 80 if you want more room
        self.txtDescription.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.cbInterfaceType = QtWidgets.QComboBox(self.grpInterface)
        self.cbInterfaceType.setMaximumWidth(DEFAULT_INPUT_WIDTH)
        self._populate_interface_type_combo()

        iface_layout.addRow("Interface name:", self.edInterfaceName)
        iface_layout.addRow("Description:", self.txtDescription)
        iface_layout.addRow("Interface type:", self.cbInterfaceType)

        main_layout.addWidget(self.grpInterface)

        # 2) TNC group
        self.grpTnc = QtWidgets.QGroupBox("Hardware TNC Setup", self)
        tnc_layout = QtWidgets.QVBoxLayout(self.grpTnc)

        # 2a) Comm Port Settings
        comm_group = QtWidgets.QGroupBox("Comm Port Settings", self.grpTnc)
        comm_form = QtWidgets.QFormLayout(comm_group)

        self.cbTncComPort = QtWidgets.QComboBox(comm_group)
        # self.cbTncComPort.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.cbTncBaud = QtWidgets.QComboBox(comm_group)
        self.cbTncBaud.setMaximumWidth(SMALL_INPUT_WIDTH)

        self.cbTncDataBits = QtWidgets.QComboBox(comm_group)
        self.cbTncDataBits.setMaximumWidth(SMALL_INPUT_WIDTH)

        self.cbTncParity = QtWidgets.QComboBox(comm_group)
        self.cbTncParity.setMaximumWidth(SMALL_INPUT_WIDTH)

        self.cbTncStopBits = QtWidgets.QComboBox(comm_group)
        self.cbTncStopBits.setMaximumWidth(SMALL_INPUT_WIDTH)

        self.cbTncFlowControl = QtWidgets.QComboBox(comm_group)
        self.cbTncFlowControl.setMaximumWidth(SMALL_INPUT_WIDTH)

        # Populate serial ports dynamically
        ports = list_serial_ports()
        ports = sorted(ports, key=lambda p: 0 if "by-id" in p else 1)
        self.cbTncComPort.addItem("")      # allow blank
        self.cbTncComPort.addItems(ports)

        self.cbTncBaud.addItems([
            "",
            "110", "300", "600", "1200", "2400",
            "4800", "9600", "14400", "19200",
            "38400", "57600", "115200",
        ])

        self.cbTncDataBits.addItems(["", "7", "8"])
        self.cbTncParity.addItems(["", "None", "Even", "Odd"])
        self.cbTncStopBits.addItems(["", "1", "2"])
        self.cbTncFlowControl.addItems(["", "None", "RTS/CTS", "XON/XOFF"])

        comm_form.addRow("Port:", self.cbTncComPort)
        comm_form.addRow("Baud:", self.cbTncBaud)
        comm_form.addRow("Data bits:", self.cbTncDataBits)
        comm_form.addRow("Parity:", self.cbTncParity)
        comm_form.addRow("Stop bits:", self.cbTncStopBits)
        comm_form.addRow("Flow control:", self.cbTncFlowControl)

        tnc_layout.addWidget(comm_group)

        # 2b) TNC Prompts
        prompts_group = QtWidgets.QGroupBox("TNC Prompts", self.grpTnc)
        prompts_form = QtWidgets.QFormLayout(prompts_group)

        self.edCmdPrompt = QtWidgets.QLineEdit(prompts_group)
        self.edCmdPrompt.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edTimeoutPrompt = QtWidgets.QLineEdit(prompts_group)
        self.edTimeoutPrompt.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edDisconnectPrompt = QtWidgets.QLineEdit(prompts_group)
        self.edDisconnectPrompt.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        prompts_form.addRow("Command prompt:", self.edCmdPrompt)
        prompts_form.addRow("Timeout prompt:", self.edTimeoutPrompt)
        prompts_form.addRow("Disconnect prompt:", self.edDisconnectPrompt)

        tnc_layout.addWidget(prompts_group)

        # 2c) TNC Commands
        cmds_group = QtWidgets.QGroupBox("TNC Commands", self.grpTnc)
        cmds_form = QtWidgets.QFormLayout(cmds_group)

        self.edMyCallCmd = QtWidgets.QLineEdit(cmds_group)
        self.edMyCallCmd.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edConnectCmd = QtWidgets.QLineEdit(cmds_group)
        self.edConnectCmd.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edConverseCmd = QtWidgets.QLineEdit(cmds_group)
        self.edConverseCmd.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edDayTimeCmd = QtWidgets.QLineEdit(cmds_group)
        self.edDayTimeCmd.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.chkIncludeTncPrefix = QtWidgets.QCheckBox(
            "Include TNC command prefix", cmds_group
        )
        self.edTncCmdPrefix = QtWidgets.QLineEdit(cmds_group)
        self.edTncCmdPrefix.setMaximumWidth(SMALL_INPUT_WIDTH)

        cmds_form.addRow("MyCall command:", self.edMyCallCmd)
        cmds_form.addRow("Connect command:", self.edConnectCmd)
        cmds_form.addRow("Converse command:", self.edConverseCmd)
        cmds_form.addRow("Day/time command:", self.edDayTimeCmd)
        cmds_form.addRow(self.chkIncludeTncPrefix)
        cmds_form.addRow("Command prefix:", self.edTncCmdPrefix)

        tnc_layout.addWidget(cmds_group)

        # 2d) TNC Init Commands
        init_group = QtWidgets.QGroupBox("TNC Init Commands", self.grpTnc)
        init_layout = QtWidgets.QVBoxLayout(init_group)

        self.chkSendInitCmds = QtWidgets.QCheckBox(
            "Send initialization commands", init_group
        )

        self.txtSendBefore = QtWidgets.QPlainTextEdit(init_group)
        self.txtSendBefore.setPlaceholderText("Commands to send BEFORE connecting…")
        self.txtSendBefore.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.txtSendAfter = QtWidgets.QPlainTextEdit(init_group)
        self.txtSendAfter.setPlaceholderText("Commands to send AFTER disconnecting…")
        self.txtSendAfter.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        init_layout.addWidget(self.chkSendInitCmds)
        init_layout.addWidget(QtWidgets.QLabel("Send before connect:", init_group))
        init_layout.addWidget(self.txtSendBefore)
        init_layout.addWidget(QtWidgets.QLabel("Send after disconnect:", init_group))
        init_layout.addWidget(self.txtSendAfter)

        tnc_layout.addWidget(init_group)

        main_layout.addWidget(self.grpTnc)

        # 3) General Network Settings
        self.grpNet = QtWidgets.QGroupBox("General Network Settings", self)
        net_form = QtWidgets.QFormLayout(self.grpNet)

        self.edRemoteHost = QtWidgets.QLineEdit(self.grpNet)
        ## self.edRemoteHost.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edRemotePort = QtWidgets.QLineEdit(self.grpNet)
        self.edRemotePort.setMaximumWidth(SMALL_INPUT_WIDTH)

        self.edNetTimeout = QtWidgets.QLineEdit(self.grpNet)
        self.edNetTimeout.setMaximumWidth(SMALL_INPUT_WIDTH)

        # Int validators for port and timeout
        int_validator = QtGui.QIntValidator(0, 65535, self)
        self.edRemotePort.setValidator(int_validator)

        timeout_validator = QtGui.QIntValidator(0, 9999999, self)
        self.edNetTimeout.setValidator(timeout_validator)
        self.edNetTimeout.setPlaceholderText("5000")

        net_form.addRow("Remote host:", self.edRemoteHost)
        net_form.addRow("Remote port:", self.edRemotePort)
        net_form.addRow("Network timeout (ms):", self.edNetTimeout)

        main_layout.addWidget(self.grpNet)

        # 4) Telnet Prompts
        self.grpTelnet = QtWidgets.QGroupBox("Telnet Prompts", self)
        tel_form = QtWidgets.QFormLayout(self.grpTelnet)

        self.edTelnetLogonPrompt = QtWidgets.QLineEdit(self.grpTelnet)
        self.edTelnetLogonPrompt.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edTelnetPasswordPrompt = QtWidgets.QLineEdit(self.grpTelnet)
        self.edTelnetPasswordPrompt.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        tel_form.addRow("Logon prompt:", self.edTelnetLogonPrompt)
        tel_form.addRow("Password prompt:", self.edTelnetPasswordPrompt)

        main_layout.addWidget(self.grpTelnet)

        # 5) AGWPE Settings
        self.grpAgwpe = QtWidgets.QGroupBox("AGWPE Settings", self)
        agw_form = QtWidgets.QFormLayout(self.grpAgwpe)

        self.edAgwRadioPort = QtWidgets.QLineEdit(self.grpAgwpe)
        self.edAgwRadioPort.setMaximumWidth(SMALL_INPUT_WIDTH)

        self.edAgwBufferSize = QtWidgets.QLineEdit(self.grpAgwpe)
        self.edAgwBufferSize.setMaximumWidth(SMALL_INPUT_WIDTH)
        self.edAgwBufferSize.setValidator(QtGui.QIntValidator(0, 9999999, self))

        self.chkAgwLogonRequired = QtWidgets.QCheckBox(
            "Logon required", self.grpAgwpe
        )
        self.edAgwLogon = QtWidgets.QLineEdit(self.grpAgwpe)
        self.edAgwLogon.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.edAgwPassword = QtWidgets.QLineEdit(self.grpAgwpe)
        self.edAgwPassword.setMaximumWidth(DEFAULT_INPUT_WIDTH)
        self.edAgwPassword.setEchoMode(QtWidgets.QLineEdit.Password)

        agw_form.addRow("Radio port:", self.edAgwRadioPort)
        agw_form.addRow("TX buffer size:", self.edAgwBufferSize)
        agw_form.addRow(self.chkAgwLogonRequired)
        agw_form.addRow("Logon:", self.edAgwLogon)
        agw_form.addRow("Password:", self.edAgwPassword)

        main_layout.addWidget(self.grpAgwpe)

        main_layout.addStretch(1)

    def _populate_interface_type_combo(self) -> None:
        """
        Populate the interface type combo with labels and enum-style userData.
        """
        self.cbInterfaceType.clear()
        self.cbInterfaceType.addItem("TNC (TAPR)", "TNC_TAPR")
        self.cbInterfaceType.addItem("TNC (SCS)", "TNC_SCS")
        self.cbInterfaceType.addItem("Telnet", "TELNET")
        self.cbInterfaceType.addItem("AGWPE", "AGWPE")

    def _connect_signals(self) -> None:
        self.cbInterfaceType.currentIndexChanged.connect(
            self._on_interface_type_changed
        )

        # Wire generic change detection for the changed signal
        def mark_changed():
            self.changed.emit()

        for widget in [
            self.edInterfaceName, self.txtDescription,
            self.cbInterfaceType,
            self.cbTncComPort, self.cbTncBaud, self.cbTncDataBits,
            self.cbTncParity, self.cbTncStopBits, self.cbTncFlowControl,
            self.edCmdPrompt, self.edTimeoutPrompt, self.edDisconnectPrompt,
            self.edMyCallCmd, self.edConnectCmd, self.edConverseCmd, self.edDayTimeCmd,
            self.chkIncludeTncPrefix, self.edTncCmdPrefix,
            self.chkSendInitCmds, self.txtSendBefore, self.txtSendAfter,
            self.edRemoteHost, self.edRemotePort, self.edNetTimeout,
            self.edTelnetLogonPrompt, self.edTelnetPasswordPrompt,
            self.edAgwRadioPort, self.edAgwBufferSize,
            self.chkAgwLogonRequired, self.edAgwLogon, self.edAgwPassword,
        ]:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textEdited.connect(mark_changed)
            elif isinstance(widget, QtWidgets.QPlainTextEdit):
                widget.textChanged.connect(mark_changed)
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(mark_changed)
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(mark_changed)

    # ------------------------------------------------------------------
    # InterfaceType handling
    # ------------------------------------------------------------------
    @QtCore.Slot(int)
    def _on_interface_type_changed(self, index: int) -> None:
        itype = self.cbInterfaceType.itemData(index)
        if not itype:
            return
        self._apply_interface_type(itype)
        self.changed.emit()

    def _apply_interface_type(self, itype: str) -> None:
        """
        Central place to control which group boxes are enabled/visible
        for each InterfaceType.
        """
        def apply_group(group: QtWidgets.QGroupBox, enabled: bool) -> None:
            if USE_HIDE_MODE:
                group.setVisible(enabled)
            else:
                group.setEnabled(enabled)

        # Defaults: everything off
        apply_group(self.grpTnc, False)
        apply_group(self.grpNet, False)
        apply_group(self.grpTelnet, False)
        apply_group(self.grpAgwpe, False)

        if itype in ("TNC_TAPR", "TNC_SCS"):
            apply_group(self.grpTnc, True)

        elif itype == "TELNET":
            apply_group(self.grpNet, True)
            apply_group(self.grpTelnet, True)

        elif itype == "AGWPE":
            apply_group(self.grpNet, True)
            apply_group(self.grpAgwpe, True)

        # Keep combo in sync if we were called programmatically
        idx = self.cbInterfaceType.findData(itype)
        if idx >= 0 and self.cbInterfaceType.currentIndex() != idx:
            self.cbInterfaceType.blockSignals(True)
            self.cbInterfaceType.setCurrentIndex(idx)
            self.cbInterfaceType.blockSignals(False)

    # ------------------------------------------------------------------
    # Public API: load/save profile
    # ------------------------------------------------------------------
    def set_profile(self, profile: InterfaceProfile) -> None:
        """
        Load all fields from a InterfaceProfile instance.
        Where the widget reads the blob and populates the UI.

        BLOB READ POINT:
        - 'profile' is the in-memory representation of the Interface JSON payload
        - At this point, JSON has already been deserialized into a dict elsewhere
        - This method only maps blob fields → UI widgets
        - That dict has already been turned into an InterfaceProfile object
    
        self.edInterfaceName.setText(profile.interface_name)
            | ui field to be loaded | profile name 
        """
        self._profile = profile

        self.edInterfaceName.setText(profile.interface_name)
        self.txtDescription.setPlainText(profile.description)

        self._apply_interface_type(profile.interface_type)

        # TNC
        self.cbTncComPort.setCurrentText(profile.tnc_com_port)
        self.cbTncBaud.setCurrentText(profile.tnc_baud)
        self.cbTncDataBits.setCurrentText(profile.tnc_data_bits)
        self.cbTncParity.setCurrentText(profile.tnc_parity)
        self.cbTncStopBits.setCurrentText(profile.tnc_stop_bits)
        self.cbTncFlowControl.setCurrentText(profile.tnc_flow_control)

        self.edCmdPrompt.setText(profile.tnc_cmd_prompt)
        self.edTimeoutPrompt.setText(profile.tnc_timeout_prompt)
        self.edDisconnectPrompt.setText(profile.tnc_disconnect_prompt)

        self.edMyCallCmd.setText(profile.tnc_mycall_cmd)
        self.edConnectCmd.setText(profile.tnc_connect_cmd)
        self.edConverseCmd.setText(profile.tnc_converse_cmd)
        self.edDayTimeCmd.setText(profile.tnc_daytime_cmd)

        self.chkIncludeTncPrefix.setChecked(profile.tnc_include_cmd_prefix)
        self.edTncCmdPrefix.setText(profile.tnc_cmd_prefix)

        self.chkSendInitCmds.setChecked(profile.tnc_send_init_cmds)
        self.txtSendBefore.setPlainText(profile.tnc_init_before)
        self.txtSendAfter.setPlainText(profile.tnc_init_after)

        # Network
        self.edRemoteHost.setText(profile.remote_host)
        self.edRemotePort.setText(profile.remote_port)
        self.edNetTimeout.setText(profile.remote_timeout)

        # Telnet
        self.edTelnetLogonPrompt.setText(profile.telnet_logon_prompt)
        self.edTelnetPasswordPrompt.setText(profile.telnet_password_prompt)

        # AGWPE
        self.edAgwRadioPort.setText(profile.agw_radio_port)
        self.edAgwBufferSize.setText(profile.agw_tx_buffer_size)
        self.chkAgwLogonRequired.setChecked(profile.agw_logon_required)
        self.edAgwLogon.setText(profile.agw_logon)
        self.edAgwPassword.setText(profile.agw_password)

    def get_profile(self) -> InterfaceProfile:
        """
        Capture UI contents into a new InterfaceProfile instance.
        Where the “blob” is created (UI → blob)

        BLOB CREATION POINT:
        - Reads every UI widgets
        - Constructs a brand-new InterfaceProfile object
        - This object is the authoritative in-memory representation of the blob

        Everything downstream (dict, JSON, DB) comes from this object.
        """
        itype = self.cbInterfaceType.currentData() or "TNC_TAPR"

        profile = InterfaceProfile(
            interface_name=self.edInterfaceName.text().strip(),
            description=self.txtDescription.toPlainText().strip(),
            interface_type=itype,

            tnc_com_port=self.cbTncComPort.currentText(),
            tnc_baud=self.cbTncBaud.currentText(),
            tnc_data_bits=self.cbTncDataBits.currentText(),
            tnc_parity=self.cbTncParity.currentText(),
            tnc_stop_bits=self.cbTncStopBits.currentText(),
            tnc_flow_control=self.cbTncFlowControl.currentText(),

            tnc_cmd_prompt=self.edCmdPrompt.text(),
            tnc_timeout_prompt=self.edTimeoutPrompt.text(),
            tnc_disconnect_prompt=self.edDisconnectPrompt.text(),

            tnc_mycall_cmd=self.edMyCallCmd.text(),
            tnc_connect_cmd=self.edConnectCmd.text(),
            tnc_converse_cmd=self.edConverseCmd.text(),
            tnc_daytime_cmd=self.edDayTimeCmd.text(),
            tnc_include_cmd_prefix=self.chkIncludeTncPrefix.isChecked(),
            tnc_cmd_prefix=self.edTncCmdPrefix.text(),

            tnc_send_init_cmds=self.chkSendInitCmds.isChecked(),
            tnc_init_before=self.txtSendBefore.toPlainText(),
            tnc_init_after=self.txtSendAfter.toPlainText(),

            remote_host=self.edRemoteHost.text(),
            remote_port=self.edRemotePort.text(),
            remote_timeout=self.edNetTimeout.text(),

            telnet_logon_prompt=self.edTelnetLogonPrompt.text(),
            telnet_password_prompt=self.edTelnetPasswordPrompt.text(),

            agw_radio_port=self.edAgwRadioPort.text(),
            agw_tx_buffer_size=self.edAgwBufferSize.text(),
            agw_logon_required=self.chkAgwLogonRequired.isChecked(),
            agw_logon=self.edAgwLogon.text(),
            agw_password=self.edAgwPassword.text(),
        )

        self._profile = profile
        return profile

    # ------------------------------------------------------------------
    # Convenience helpers for integration with repos/JSON/DB
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the current InterfaceProfile blob to a plain dictionary.
        Where the blob becomes a dict (pre-JSON)

        BLOB SERIALIZATION (PRE-JSON):
        - Uses dataclasses.asdict()
        - Keys exactly match InterfaceProfile field names
        - This dict is what gets JSON-encoded by the repository

        UI ends here
        Persistence begins after this
        """
        return asdict(self.get_profile())

    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load an InterfaceProfile blob from a dictionary.

        BLOB RECONSTRUCTION POINT:
        - 'data' typically comes from JSON stored in SQLite
        - Missing keys are filled with dataclass defaults
        - Resulting InterfaceProfile is pushed into the UI
        """
        profile = InterfaceProfile(**{**asdict(InterfaceProfile()), **data})
        self.set_profile(profile)

    # ------------------------------------------------------------------
    # Default TNC profile helper
    # ------------------------------------------------------------------
    def make_default_tnc_profile(self) -> InterfaceProfile:
        """
        Create a new InterfaceProfile with reasonable defaults.

        BLOB FACTORY:
        - Creates a complete InterfaceProfile programmatically
        - Used for 'New Interface' or template creation

        NOTE: These are placeholder defaults. Adjust them to exactly
        match the IRS page 44/47 values.
        """
        profile = InterfaceProfile()

        # Basic identity
        profile.interface_name = "New TNC Interface"
        profile.description = ""
        profile.interface_type = "TNC_TAPR"  # or "TNC_SCS" if you prefer

        # Comm port defaults (this is just a hint; user will pick a real /dev/tty*)
        profile.tnc_com_port = ""
        profile.tnc_baud = "9600"
        profile.tnc_data_bits = "8"
        profile.tnc_parity = "None"
        profile.tnc_stop_bits = "1"
        profile.tnc_flow_control = "None"

        # Prompts (tune to IRS specifics)
        profile.tnc_cmd_prompt = "cmd:"
        profile.tnc_timeout_prompt = "*** retry count exceeded"
        profile.tnc_disconnect_prompt = "*** DISCONNECTED"

        # Commands (tune as needed)
        profile.tnc_mycall_cmd = "MYCALL"
        profile.tnc_connect_cmd = "C"
        profile.tnc_converse_cmd = "CONV"
        profile.tnc_daytime_cmd = "DAYTIME"
        profile.tnc_include_cmd_prefix = False
        profile.tnc_cmd_prefix = ""  # e.g., "@" if you use a prefix

        # Init commands (off by default)
        profile.tnc_send_init_cmds = False
        profile.tnc_init_before = ""
        profile.tnc_init_after = ""

        # Network timeout - 5000 ms as you mentioned
        profile.remote_timeout = "5000"

        # Telnet / AGWPE left blank by default
        # (They won’t matter when interface_type is TNC_*)

        return profile

    def load_default_tnc_profile(self) -> None:
        """
        Convenience: create a default TNC profile and load it into the UI.
        """
        profile = self.make_default_tnc_profile()
        self.set_profile(profile)


# ----------------------------------------------------------------------
# Manual test harness
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = InterfaceSetupWidget()
    w.resize(800, 700)
    w.show()
    sys.exit(app.exec())
