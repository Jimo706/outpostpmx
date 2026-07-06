from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets, QtCore

from data.bbs_profile_model import BBSProfile

# Standard width to keep fields from stretching too wide (esp. on Linux)
DEFAULT_INPUT_WIDTH = 300


class BBSSettingsWidget(QtWidgets.QWidget):
    """Editor widget for a single :class:`BBSProfile`.

    Implements the layout described in the OutpostX IRS (section 7.2):

        * Basics
        * BBS Commands
        * Init Commands
        * Retrieve Options
        * Path Options

    The widget is *purely* a UI/view: it does not talk to SQLite directly.
    Call :meth:`load_profile` to populate the form and :meth:`apply_to_profile`
    to push changes back into a :class:`BBSProfile` instance.
    """

    changed = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        root = QtWidgets.QVBoxLayout(self)
        
        # --------------------------------------------------------------
        # Basics
        # --------------------------------------------------------------
        basics_group = QtWidgets.QGroupBox("BBS Definition")
        basics_group.setStyleSheet("QGroupBox { font-weight: bold; }")  # makes label BOLD
        fb = QtWidgets.QFormLayout(basics_group)
        fb.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self._bbs_profile_id: int | None = None

        self.ed_friendly_name = QtWidgets.QLineEdit()
        self.ed_friendly_name.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_connect_call = QtWidgets.QLineEdit()
        self.ed_connect_call.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.txt_description = QtWidgets.QPlainTextEdit()
        self.txt_description.setMinimumHeight(60)
        self.txt_description.setTabChangesFocus(True)   # allows tab to tab to the next field
        self.txt_description.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        fb.addRow("Friendly name:", self.ed_friendly_name)
        fb.addRow("Connect call:", self.ed_connect_call)
        fb.addRow("Description:", self.txt_description)

        root.addWidget(basics_group)

        # --------------------------------------------------------------
        # BBS Commands
        # --------------------------------------------------------------
        cmd_group = QtWidgets.QGroupBox("BBS Commands")
        fc = QtWidgets.QFormLayout(cmd_group)
        fc.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self.ed_cmd_send_private = QtWidgets.QLineEdit()
        self.ed_cmd_send_private.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_send_bcast = QtWidgets.QLineEdit()
        self.ed_cmd_send_bcast.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_send_nts = QtWidgets.QLineEdit()
        self.ed_cmd_send_nts.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_list_mine = QtWidgets.QLineEdit()
        self.ed_cmd_list_mine.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_list_bcast = QtWidgets.QLineEdit()
        self.ed_cmd_list_bcast.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_list_nts = QtWidgets.QLineEdit()
        self.ed_cmd_list_nts.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_list_filtered = QtWidgets.QLineEdit()
        self.ed_cmd_list_filtered.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_read_msg = QtWidgets.QLineEdit()
        self.ed_cmd_read_msg.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_kill_msg = QtWidgets.QLineEdit()
        self.ed_cmd_kill_msg.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        self.ed_cmd_bye = QtWidgets.QLineEdit()
        self.ed_cmd_bye.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        fc.addRow("Send:", self.ed_cmd_send_private)
        fc.addRow("Send bulletin:", self.ed_cmd_send_bcast)
        fc.addRow("Send NTS:", self.ed_cmd_send_nts)
        fc.addRow("List mine:", self.ed_cmd_list_mine)
        fc.addRow("List bulletins:", self.ed_cmd_list_bcast)
        fc.addRow("List NTS:", self.ed_cmd_list_nts)
        fc.addRow("List filtered:", self.ed_cmd_list_filtered)
        fc.addRow("Read:", self.ed_cmd_read_msg)
        fc.addRow("Delete:", self.ed_cmd_kill_msg)
        fc.addRow("Bye:", self.ed_cmd_bye)

        root.addWidget(cmd_group)

        # --------------------------------------------------------------
        # Init Commands
        # --------------------------------------------------------------
        init_group = QtWidgets.QGroupBox("Init Commands")
        vi = QtWidgets.QVBoxLayout(init_group)

        self.rb_init_never = QtWidgets.QRadioButton(
            "Never send BBS init commands"
        )
        self.rb_init_always = QtWidgets.QRadioButton(
            "Always send BBS init commands"
        )
        self.rb_init_always.setChecked(True)

        vi.addWidget(self.rb_init_never)
        vi.addWidget(self.rb_init_always)

        vi.addWidget(QtWidgets.QLabel("Sent before send/receive:"))
        self.txt_cmd_before = QtWidgets.QPlainTextEdit()
        self.txt_cmd_before.setMinimumHeight(60)
        self.txt_cmd_before.setTabChangesFocus(True)    # allows tab to tab to the next field
        self.txt_cmd_before.setMaximumWidth(DEFAULT_INPUT_WIDTH)
        vi.addWidget(self.txt_cmd_before)

        vi.addWidget(QtWidgets.QLabel("Sent after send/receive:"))
        self.txt_cmd_after = QtWidgets.QPlainTextEdit()
        self.txt_cmd_after.setMinimumHeight(60)
        self.txt_cmd_after.setTabChangesFocus(True)    # allows tab to tab to the next field
        self.txt_cmd_after.setMaximumWidth(DEFAULT_INPUT_WIDTH)
        vi.addWidget(self.txt_cmd_after)

        root.addWidget(init_group)

        # --------------------------------------------------------------
        # Retrieve Options
        # --------------------------------------------------------------
        retr_group = QtWidgets.QGroupBox("Retrieve Options")
        vr = QtWidgets.QVBoxLayout(retr_group)

        grid = QtWidgets.QGridLayout()
        self.chk_retrieve_private = QtWidgets.QCheckBox("Retrieve private messages")
        self.chk_delete_on_bbs = QtWidgets.QCheckBox("Delete after downloading")
        self.chk_retrieve_nts = QtWidgets.QCheckBox("Retrieve NTS messages")
        self.chk_skip_my_nts = QtWidgets.QCheckBox("Skip my NTS messages")
        self.chk_retrieve_bulletins = QtWidgets.QCheckBox("Retrieve bulletins")
        self.chk_skip_my_bulletins = QtWidgets.QCheckBox("Skip my bulletins")

        grid.addWidget(self.chk_retrieve_private, 0, 0)
        grid.addWidget(self.chk_delete_on_bbs, 0, 1)
        grid.addWidget(self.chk_retrieve_nts, 1, 0)
        grid.addWidget(self.chk_skip_my_nts, 1, 1)
        grid.addWidget(self.chk_retrieve_bulletins, 2, 0)
        grid.addWidget(self.chk_skip_my_bulletins, 2, 1)

        vr.addLayout(grid)

        # Bulletins sub-options
        bc_group = QtWidgets.QGroupBox("Retrieve bulletins")
        vbc = QtWidgets.QVBoxLayout(bc_group)

        self.rb_bc_all = QtWidgets.QRadioButton("All new bulletins")
        self.rb_bc_selected = QtWidgets.QRadioButton("Selected bulletins")
        self.rb_bc_custom = QtWidgets.QRadioButton("Custom retrieval (JNOS)")

        self.rb_bc_all.setChecked(True)

        vbc.addWidget(self.rb_bc_all)
        vbc.addWidget(self.rb_bc_selected)

        self.txt_retrieve_selected = QtWidgets.QPlainTextEdit()
        self.txt_retrieve_selected.setPlaceholderText("EQUAKE, ARES")
        self.txt_retrieve_selected.setMinimumHeight(50)
        self.txt_retrieve_selected.setTabChangesFocus(True)     # allows tab to tab to the next field
        self.txt_retrieve_selected.setMaximumWidth(DEFAULT_INPUT_WIDTH)
        vbc.addWidget(self.txt_retrieve_selected)

        vbc.addWidget(self.rb_bc_custom)

        self.txt_retrieve_custom = QtWidgets.QPlainTextEdit()
        self.txt_retrieve_custom.setPlaceholderText("# JNOS commands")
        self.txt_retrieve_custom.setTabChangesFocus(True)     # allows tab to tab to the next field
        self.txt_retrieve_custom.setMaximumWidth(DEFAULT_INPUT_WIDTH)
        vbc.addWidget(self.txt_retrieve_custom)

        vr.addWidget(bc_group)

        root.addWidget(retr_group)

        # --------------------------------------------------------------
        # Path Options
        # --------------------------------------------------------------
        path_group = QtWidgets.QGroupBox("Path Options")
        vp = QtWidgets.QVBoxLayout(path_group)

        self.rb_path_direct = QtWidgets.QRadioButton("Direct")
        self.rb_path_via = QtWidgets.QRadioButton("Via digipeater(s)")
        self.rb_path_node = QtWidgets.QRadioButton("SCRIPT (KA-NODE / Netrom)")

        self.rb_path_direct.setChecked(True)

        vp.addWidget(self.rb_path_direct)
        vp.addWidget(self.rb_path_via)

        via_row = QtWidgets.QHBoxLayout()
        via_row.addSpacing(24)
        via_row.addWidget(QtWidgets.QLabel("Digipeater path:"))
        self.ed_path_via = QtWidgets.QLineEdit()
        self.ed_path_via.setMaximumWidth(DEFAULT_INPUT_WIDTH)
        via_row.addWidget(self.ed_path_via, 1)
        vp.addLayout(via_row)

        vp.addWidget(self.rb_path_node)

        # ------------------------------------------------------------------
        # SCRIPT / Node Path editor
        # ------------------------------------------------------------------
        self.lbl_path_script_timeout = QtWidgets.QLabel("Script Timeout:")
        self.ed_path_script_timeout = QtWidgets.QLineEdit()
        self.ed_path_script_timeout.setMaximumWidth(80)
        self.lbl_path_script_timeout_units = QtWidgets.QLabel("seconds")

        timeout_row = QtWidgets.QHBoxLayout()
        timeout_row.addSpacing(24)
        timeout_row.addWidget(self.lbl_path_script_timeout)
        timeout_row.addWidget(self.ed_path_script_timeout)
        timeout_row.addWidget(self.lbl_path_script_timeout_units)
        timeout_row.addStretch(1)

        self.w_path_script_timeout = QtWidgets.QWidget()
        self.w_path_script_timeout.setLayout(timeout_row)

        self.lbl_path_script = QtWidgets.QLabel("Script Editor:")
        self.txt_path_script = QtWidgets.QPlainTextEdit()
        self.txt_path_script.setPlaceholderText(
            '# Example:\n'
            'SEND "BBS"\n'
        )
        # Add size policy to allow path_script to expand to the available space allowable.
        # This means we do not need 'self.txt_path_script.setMaximumWidth(DEFAULT_INPUT_WIDTH)'.
        self.txt_path_script.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,     # Horizontal Policy, and use of extra horizontal space
            QtWidgets.QSizePolicy.Policy.Preferred,     # Vertical Policy, widget has a "preferred" height & is undesirable to stretch
        )
        self.txt_path_script.setMinimumHeight(120)
        self.txt_path_script.setTabChangesFocus(True)
        # self.txt_path_script.setMaximumWidth(DEFAULT_INPUT_WIDTH)

        script_label_row = QtWidgets.QHBoxLayout()
        script_label_row.addSpacing(24)
        script_label_row.addWidget(self.lbl_path_script)
        script_label_row.addStretch(1)

        self.w_path_script_label = QtWidgets.QWidget()
        self.w_path_script_label.setLayout(script_label_row)

        script_edit_row = QtWidgets.QHBoxLayout()
        script_edit_row.addSpacing(24)
        script_edit_row.addWidget(self.txt_path_script, 1)

        self.w_path_script_edit = QtWidgets.QWidget()
        self.w_path_script_edit.setLayout(script_edit_row)

        self.btn_load_script_example = QtWidgets.QPushButton("Load Example")
        self.btn_validate_script = QtWidgets.QPushButton("Validate")
        self.btn_clear_script = QtWidgets.QPushButton("Clear")

        script_btn_row = QtWidgets.QHBoxLayout()
        script_btn_row.addSpacing(24)
        script_btn_row.addWidget(self.btn_load_script_example)
        script_btn_row.addWidget(self.btn_validate_script)
        script_btn_row.addWidget(self.btn_clear_script)
        script_btn_row.addStretch(1)

        self.w_path_script_buttons = QtWidgets.QWidget()
        self.w_path_script_buttons.setLayout(script_btn_row)

        vp.addWidget(self.w_path_script_timeout)
        vp.addWidget(self.w_path_script_label)
        vp.addWidget(self.w_path_script_edit)
        vp.addWidget(self.w_path_script_buttons)

        root.addWidget(path_group)
        root.addStretch(1)

        # Wire up simple enable/disable behavior
        self.rb_bc_all.toggled.connect(self._update_bulletin_mode)
        self.rb_bc_selected.toggled.connect(self._update_bulletin_mode)
        self.rb_bc_custom.toggled.connect(self._update_bulletin_mode)
        self._update_bulletin_mode()

        self.rb_path_direct.toggled.connect(self._update_path_mode)
        self.rb_path_via.toggled.connect(self._update_path_mode)
        self.rb_path_node.toggled.connect(self._update_path_mode)

        self.btn_load_script_example.clicked.connect(self._on_load_script_example)
        self.btn_validate_script.clicked.connect(self._on_validate_script)
        self.btn_clear_script.clicked.connect(self._on_clear_script)

        self._update_path_mode()

        self._wire_change_tracking()
        self._wire_uppercase_fields()

        # --------------------------------------------------------------
        # horizontal shrink management
        # --------------------------------------------------------------
        # Encourage group boxes and fields to shrink/grow with the dialog
        for grp in (basics_group, cmd_group, init_group, retr_group, path_group):
            grp.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Preferred,
            )

        line_edits = [
            self.ed_friendly_name,
            self.ed_connect_call,
            self.ed_cmd_send_private,
            self.ed_cmd_send_bcast,
            self.ed_cmd_send_nts,
            self.ed_cmd_list_mine,
            self.ed_cmd_list_bcast,
            self.ed_cmd_list_nts,
            self.ed_cmd_list_filtered,
            self.ed_cmd_read_msg,
            self.ed_cmd_kill_msg,
            self.ed_cmd_bye,
            self.ed_path_via,
        ]
        for edit in line_edits:
            edit.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred,
                QtWidgets.QSizePolicy.Fixed,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_profile(
        self,
        profile: BBSProfile,
        interfaces: list[str] | None = None,
    ) -> None:
        """Populate the form from a :class:`BBSProfile` instance.

        ``interfaces`` is an optional list of interface names to show in the
        Interface combobox. If provided, the profile's interface_name will be
        selected when possible.
        """
        self._profile = profile
        self._bbs_profile_id = profile.id

        self.ed_friendly_name.setText(profile.friendly_name)
        self.ed_connect_call.setText(profile.connect_call)
        self.txt_description.setPlainText(profile.description)

        # Commands
        self.ed_cmd_send_private.setText(profile.cmd_send_private)
        self.ed_cmd_send_bcast.setText(profile.cmd_send_bcast)
        self.ed_cmd_send_nts.setText(profile.cmd_send_nts)
        self.ed_cmd_list_mine.setText(profile.cmd_list_mine)
        self.ed_cmd_list_bcast.setText(profile.cmd_list_bcast)
        self.ed_cmd_list_nts.setText(profile.cmd_list_nts)
        self.ed_cmd_list_filtered.setText(profile.cmd_list_filtered)
        self.ed_cmd_read_msg.setText(profile.cmd_read_msg)
        self.ed_cmd_kill_msg.setText(profile.cmd_kill_msg)
        self.ed_cmd_bye.setText(profile.cmd_bye)

        # Init
        if profile.use_init_cmd:
            self.rb_init_always.setChecked(True)
        else:
            self.rb_init_never.setChecked(True)
        self.txt_cmd_before.setPlainText(profile.cmd_before)
        self.txt_cmd_after.setPlainText(profile.cmd_after)

        # Retrieve
        self.chk_retrieve_private.setChecked(profile.retrieve_private)
        self.chk_retrieve_nts.setChecked(profile.retrieve_nts)
        self.chk_retrieve_bulletins.setChecked(profile.retrieve_bulletins)
        self.chk_delete_on_bbs.setChecked(profile.delete_on_bbs)
        self.chk_skip_my_nts.setChecked(profile.skip_my_nts)
        self.chk_skip_my_bulletins.setChecked(profile.skip_my_bulletins)

        self.txt_path_script.setPlainText(profile.path_script or "")
        self.ed_path_script_timeout.setText(profile.path_script_timeout or "")        

        mode = profile.retrieve_bulletins_mode.upper()
        if mode == "SELECTED":
            self.rb_bc_selected.setChecked(True)
        elif mode == "CUSTOM":
            self.rb_bc_custom.setChecked(True)
        else:
            self.rb_bc_all.setChecked(True)

        self.txt_retrieve_selected.setPlainText(profile.retrieve_selected)
        self.txt_retrieve_custom.setPlainText(profile.retrieve_custom)

        # Path
        ptype = profile.path_type.upper()
        if ptype == "VIA":
            self.rb_path_via.setChecked(True)
        elif ptype == "NODE":
            self.rb_path_node.setChecked(True)
        else:
            self.rb_path_direct.setChecked(True)

        self.ed_path_via.setText(profile.path_via or profile.digipeater_list)

        self._update_bulletin_mode()
        self._update_path_mode()

    def apply_to_profile(self, profile: Optional[BBSProfile] = None) -> BBSProfile:
        """Update ``profile`` from the form and return it.

        If ``profile`` is None, the last one passed to :meth:`load_profile`
        will be used.
        """
        if profile is None:
            profile = getattr(self, "_profile", None)
        if profile is None:
            profile = BBSProfile()

        profile.friendly_name = self.ed_friendly_name.text().strip()
        profile.connect_call = self.ed_connect_call.text().strip().upper()
        profile.description = self.txt_description.toPlainText().strip()

        profile.cmd_send_private = (
            self.ed_cmd_send_private.text().strip().upper() or "SP"
        )
        profile.cmd_send_bcast = (
            self.ed_cmd_send_bcast.text().strip().upper() or "SB"
        )
        profile.cmd_send_nts = (
            self.ed_cmd_send_nts.text().strip().upper() or "ST"
        )
        profile.cmd_list_mine = (
            self.ed_cmd_list_mine.text().strip().upper() or "LM"
        )
        profile.cmd_list_bcast = (
            self.ed_cmd_list_bcast.text().strip().upper() or "LB"
        )
        profile.cmd_list_nts = (
            self.ed_cmd_list_nts.text().strip().upper() or "LT"
        )
        profile.cmd_list_filtered = (
            self.ed_cmd_list_filtered.text().strip().upper() or "L>"
        )
        profile.cmd_read_msg = (
            self.ed_cmd_read_msg.text().strip().upper() or "R"
        )
        profile.cmd_kill_msg = (
            self.ed_cmd_kill_msg.text().strip().upper() or "K"
        )
        profile.cmd_bye = self.ed_cmd_bye.text().strip().upper() or "B"

        profile.use_init_cmd = self.rb_init_always.isChecked()
        profile.cmd_before = self.txt_cmd_before.toPlainText().strip()
        profile.cmd_after = self.txt_cmd_after.toPlainText().strip()

        profile.retrieve_private = self.chk_retrieve_private.isChecked()
        profile.retrieve_nts = self.chk_retrieve_nts.isChecked()
        profile.retrieve_bulletins = self.chk_retrieve_bulletins.isChecked()
        profile.delete_on_bbs = self.chk_delete_on_bbs.isChecked()
        profile.skip_my_nts = self.chk_skip_my_nts.isChecked()
        profile.skip_my_bulletins = self.chk_skip_my_bulletins.isChecked()

        if self.rb_bc_selected.isChecked():
            profile.retrieve_bulletins_mode = "SELECTED"
        elif self.rb_bc_custom.isChecked():
            profile.retrieve_bulletins_mode = "CUSTOM"
        else:
            profile.retrieve_bulletins_mode = "ALL"

        profile.retrieve_selected = (
            self.txt_retrieve_selected.toPlainText().upper().strip()
        )
        profile.retrieve_custom = self.txt_retrieve_custom.toPlainText().strip()

        if self.rb_path_via.isChecked():
            profile.path_type = "VIA"
        elif self.rb_path_node.isChecked():
            profile.path_type = "NODE"
        else:
            profile.path_type = "DIRECT"

        profile.path_via = self.ed_path_via.text().strip().upper()
        profile.digipeater_list = profile.path_via

        ###vvv+++
        profile.path_script = self.txt_path_script.toPlainText().strip()
        profile.path_script_timeout = self.ed_path_script_timeout.text().strip()        
        ### ^^^+++

        return profile


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_bulletin_mode(self) -> None:
        self.txt_retrieve_selected.setEnabled(self.rb_bc_selected.isChecked())
        self.txt_retrieve_custom.setEnabled(self.rb_bc_custom.isChecked())

    def _update_path_mode(self) -> None:
        self.ed_path_via.setEnabled(self.rb_path_via.isChecked())

        ###vvv+++
        is_direct = self.rb_path_direct.isChecked()
        is_via = self.rb_path_via.isChecked()
        is_script = self.rb_path_node.isChecked()   # keep old variable name for now

        self.ed_path_via.setEnabled(is_via)

        self.w_path_script_timeout.setEnabled(is_script)
        self.txt_path_script.setEnabled(is_script)
        self.w_path_script_buttons.setEnabled(is_script)

        self.lbl_path_script_timeout.setEnabled(is_script)
        self.ed_path_script_timeout.setEnabled(is_script)
        self.lbl_path_script_timeout_units.setEnabled(is_script)
        self.lbl_path_script.setEnabled(is_script)
        ###^^^+++

    def _wire_uppercase_fields(self) -> None:
        """Uppercase certain fields when the user leaves them."""
        line_edits = [
            self.ed_connect_call,
            self.ed_cmd_send_private,
            self.ed_cmd_send_bcast,
            self.ed_cmd_send_nts,
            self.ed_cmd_list_mine,
            self.ed_cmd_list_bcast,
            self.ed_cmd_list_nts,
            self.ed_cmd_list_filtered,
            self.ed_cmd_read_msg,
            self.ed_cmd_kill_msg,
            self.ed_cmd_bye,
            self.ed_path_via,
        ]
        for edit in line_edits:
            edit.editingFinished.connect(self._uppercase_sender)

    def _uppercase_sender(self) -> None:
        w = self.sender()
        if isinstance(w, QtWidgets.QLineEdit):
            w.setText(w.text().upper())

    def _wire_change_tracking(self) -> None:
        """Emit `changed` whenever any relevant field is modified."""
        text_widgets = [
            self.ed_friendly_name,
            self.ed_connect_call,
            self.txt_description,
            self.ed_cmd_send_private,
            self.ed_cmd_send_bcast,
            self.ed_cmd_send_nts,
            self.ed_cmd_list_mine,
            self.ed_cmd_list_bcast,
            self.ed_cmd_list_nts,
            self.ed_cmd_list_filtered,
            self.ed_cmd_read_msg,
            self.ed_cmd_kill_msg,
            self.ed_cmd_bye,
            self.txt_cmd_before,
            self.txt_cmd_after,
            self.txt_retrieve_selected,
            self.txt_retrieve_custom,
            self.ed_path_via,
            self.txt_path_script,
            self.ed_path_script_timeout,            
        ]
        for w in text_widgets:
            if isinstance(w, QtWidgets.QLineEdit):
                w.textChanged.connect(self.changed)
            else:  # QPlainTextEdit
                w.textChanged.connect(self.changed)

        check_widgets = [
            self.chk_retrieve_private,
            self.chk_delete_on_bbs,
            self.chk_retrieve_nts,
            self.chk_skip_my_nts,
            self.chk_retrieve_bulletins,
            self.chk_skip_my_bulletins,
        ]
        for w in check_widgets:
            w.toggled.connect(self.changed)

        radio_widgets = [
            self.rb_init_never,
            self.rb_init_always,
            self.rb_bc_all,
            self.rb_bc_selected,
            self.rb_bc_custom,
            self.rb_path_direct,
            self.rb_path_via,
            self.rb_path_node,
        ]
        for w in radio_widgets:
            w.toggled.connect(self.changed)

    # 260421: updated for new WAITFOR pattern
    def _on_load_script_example(self) -> None:
        example = (
            '# Example script to enter the BBS from a node\n'
            'TIMEOUT 10\n'
            'SEND "C ROCK"\n'
            'WAITFOR OK "Help ?" FAIL "*** RET", "*** DISCONNECTED"\n'
            'SEND "BBS"\n'
        )
        self.txt_path_script.setPlainText(example)

        if not (self.ed_path_script_timeout.text() or "").strip():
            self.ed_path_script_timeout.setText("15")

        self.changed.emit()

    def _on_clear_script(self) -> None:
        self.txt_path_script.clear()
        self.ed_path_script_timeout.clear()
        self.changed.emit()


    def _on_validate_script(self) -> None:
        script_text = self.txt_path_script.toPlainText()
        timeout_text = (self.ed_path_script_timeout.text() or "").strip()

        errors: list[str] = []

        # Validate timeout
        if timeout_text:
            if not timeout_text.isdigit() or int(timeout_text) <= 0:
                errors.append("Timeout must be a positive integer number of seconds.")

        lines = script_text.splitlines()

        import re
        re_send = re.compile(r'^\s*SEND\s+"[^"]*"\s*$', re.IGNORECASE)
        re_waitfor = re.compile(
            r'^\s*WAITFOR\s+OK\s+"[^"]*"(?:\s*,\s*"[^"]*")*\s+FAIL\s+"[^"]*"(?:\s*,\s*"[^"]*")*\s*$',
            re.IGNORECASE,
        )
        re_timeout = re.compile(r'^\s*TIMEOUT\s+\d+\s*$', re.IGNORECASE)
        re_comment = re.compile(r'^\s*#.*$')
        re_blank = re.compile(r'^\s*$')

        for lineno, raw in enumerate(lines, start=1):
            line = raw.rstrip()

            if re_blank.match(line):
                continue
            if re_comment.match(line):
                continue
            if re_send.match(line):
                continue
            if re_waitfor.match(line):
                continue
            if re_timeout.match(line):
                continue

            errors.append(f"Line {lineno}: invalid script syntax: {line}")

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Validate Script",
                "The script has errors:\n\n" + "\n".join(errors),
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Validate Script",
                "Script format looks valid.",
            )
