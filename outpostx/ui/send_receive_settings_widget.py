# ui/send_receive_settings_widget.py
from __future__ import annotations

from typing import List, Optional

from PySide6 import QtWidgets, QtCore

from services.send_receive_settings import (
    SendReceiveSettings,
    AutomationMode,
)
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import QUrl



class SendReceiveSettingsWidget(QtWidgets.QWidget):
    """
    Global Send/Receive Settings UI.

    - Automation:
        * Manual
        * Every N minutes
        * Slot Time Scheduling (multiple minutes past the hour)
    - When receiving:
        * Optional sound on message arrival
    - Printing:
        * Optional printing of received/sent/receipt/plain-text headers
    """

    changed = QtCore.Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_settings: Optional[SendReceiveSettings] = None
        

        self._build_ui()
        self._wire_signals()
        self._test_sound = QSoundEffect(self)
        self._test_sound.setVolume(0.5)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # ------------------------------------------------------------------
        # Group: Automation
        # ------------------------------------------------------------------
        grp_auto = QtWidgets.QGroupBox("Automation", self)
        va = QtWidgets.QVBoxLayout(grp_auto)

        # Radio buttons
        self.rbManual = QtWidgets.QRadioButton("Manual.  Initiate each send/receive session manually")
        self.rbEveryN = QtWidgets.QRadioButton("Schedule a Send/Receive every N minutes")
        self.rbSlots = QtWidgets.QRadioButton("Schedule a Send/Receive every \"#\" minutes past the hour")

        # Every N minutes controls
        row_every = QtWidgets.QHBoxLayout()
        row_every.setContentsMargins(24, 0, 0, 0)  # indent under radio
        self.spinInterval = QtWidgets.QSpinBox()
        self.spinInterval.setRange(1, 1440)
        self.spinInterval.setValue(15)
        row_every.addWidget(QtWidgets.QLabel("Run every", self))
        row_every.addWidget(self.spinInterval)
        row_every.addWidget(QtWidgets.QLabel("minutes", self))
        row_every.addStretch(1)

        # Slot Time controls
        row_slots = QtWidgets.QVBoxLayout()
        row_slots.setContentsMargins(24, 0, 0, 0)  # indent under radio

        self.edSlots = QtWidgets.QLineEdit()
        self.edSlots.setPlaceholderText("e.g. 5, 45, 59")

        self.lblSlotsHint = QtWidgets.QLabel(
            "Hint: Enter 1 or more as a list of minutes separated by commas (i.e.: 5, 45, 59).",
            self,
        )
        self.lblSlotsHint.setWordWrap(True)

        row_slots.addWidget(QtWidgets.QLabel("Minutes past the hour (0–59):", self))
        row_slots.addWidget(self.edSlots)
        row_slots.addWidget(self.lblSlotsHint)

        va.addWidget(self.rbManual)
        va.addWidget(self.rbEveryN)
        va.addLayout(row_every)
        va.addWidget(self.rbSlots)
        va.addLayout(row_slots)

        layout.addWidget(grp_auto)

        # ------------------------------------------------------------------
        # Group: When Receiving
        # ------------------------------------------------------------------
        grp_recv = QtWidgets.QGroupBox("When receiving", self)
        vr = QtWidgets.QVBoxLayout(grp_recv)

        self.chkPlaySound = QtWidgets.QCheckBox("Play this sound on message arrival", self)

        row_sound = QtWidgets.QHBoxLayout()
        self.edSoundPath = QtWidgets.QLineEdit()
        self.btnBrowseSound = QtWidgets.QPushButton("Browse")
        self.btnTestSound = QtWidgets.QPushButton("Test")
        row_sound.addWidget(self.edSoundPath, 1)
        row_sound.addWidget(self.btnBrowseSound)
        row_sound.addWidget(self.btnTestSound)

        vr.addWidget(self.chkPlaySound)
        vr.addLayout(row_sound)

        layout.addWidget(grp_recv)

        # ------------------------------------------------------------------
        # Group: Printing
        # ------------------------------------------------------------------
        grp_print = QtWidgets.QGroupBox("Printing", self)
        vp = QtWidgets.QVBoxLayout(grp_print)

        # Print received
        row_prx = QtWidgets.QHBoxLayout()
        self.chkPrintReceived = QtWidgets.QCheckBox("Print received messages", self)
        self.spinPrintReceived = QtWidgets.QSpinBox()
        self.spinPrintReceived.setRange(1, 9)
        self.spinPrintReceived.setValue(3)  # matches your mockup
        row_prx.addWidget(self.chkPrintReceived)
        row_prx.addSpacing(8)
        row_prx.addWidget(self.spinPrintReceived)
        row_prx.addWidget(QtWidgets.QLabel("copies (max 9)", self))
        row_prx.addStretch(1)

        # Print sent
        row_psx = QtWidgets.QHBoxLayout()
        self.chkPrintSent = QtWidgets.QCheckBox("Print sent messages", self)
        self.spinPrintSent = QtWidgets.QSpinBox()
        self.spinPrintSent.setRange(1, 9)
        self.spinPrintSent.setValue(1)
        row_psx.addWidget(self.chkPrintSent)
        row_psx.addSpacing(8)
        row_psx.addWidget(self.spinPrintSent)
        row_psx.addWidget(QtWidgets.QLabel("copies (max 9)", self))
        row_psx.addStretch(1)

        self.chkPrintReceipts = QtWidgets.QCheckBox("Print Receipt messages", self)
        self.chkPrintPlainHeaders = QtWidgets.QCheckBox(
            "Print headers for plain text messages (not forms)",
            self,
        )

        vp.addLayout(row_prx)
        vp.addLayout(row_psx)
        vp.addWidget(self.chkPrintReceipts)
        vp.addWidget(self.chkPrintPlainHeaders)

        layout.addWidget(grp_print)
        layout.addStretch(1)

        # Defaults
        self.rbManual.setChecked(True)
        self._update_mode_controls()
        self._update_print_controls()
        self._update_sound_controls()

    def _wire_signals(self) -> None:
        # Automation
        self.rbManual.toggled.connect(self._on_mode_toggled)
        self.rbEveryN.toggled.connect(self._on_mode_toggled)
        self.rbSlots.toggled.connect(self._on_mode_toggled)
        self.spinInterval.valueChanged.connect(self._on_changed)
        self.edSlots.textChanged.connect(self._on_changed)

        # When receiving
        self.chkPlaySound.toggled.connect(self._on_sound_toggled)
        self.edSoundPath.textChanged.connect(self._on_changed)
        self.btnBrowseSound.clicked.connect(self._on_browse_sound)
        self.btnTestSound.clicked.connect(self._on_test_sound)

        # Printing
        self.chkPrintReceived.toggled.connect(self._on_print_toggled)
        self.spinPrintReceived.valueChanged.connect(self._on_changed)
        self.chkPrintSent.toggled.connect(self._on_print_toggled)
        self.spinPrintSent.valueChanged.connect(self._on_changed)
        self.chkPrintReceipts.toggled.connect(self._on_changed)
        self.chkPrintPlainHeaders.toggled.connect(self._on_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_from_models(self, settings: SendReceiveSettings) -> None:
        """
        Populate the widget from a SendReceiveSettings instance.
        """
        self._current_settings = settings

        # Automation mode
        if settings.mode == AutomationMode.MANUAL:
            self.rbManual.setChecked(True)
        elif settings.mode == AutomationMode.EVERY_N_MINUTES:
            self.rbEveryN.setChecked(True)
        else:
            self.rbSlots.setChecked(True)

        self.spinInterval.setValue(max(1, settings.interval_minutes))

        # Slot minutes: format as comma-separated list
        if settings.slot_minutes:
            text = ", ".join(str(s) for s in sorted(set(settings.slot_minutes)))
        else:
            text = ""
        self.edSlots.setText(text)

        # When receiving
        self.chkPlaySound.setChecked(settings.play_sound_on_receive)
        self.edSoundPath.setText(settings.sound_file_path or "")

        # Printing
        self.chkPrintReceived.setChecked(settings.print_received)
        self.spinPrintReceived.setValue(settings.print_received_copies)
        self.chkPrintSent.setChecked(settings.print_sent)
        self.spinPrintSent.setValue(settings.print_sent_copies)
        self.chkPrintReceipts.setChecked(settings.print_receipts)
        self.chkPrintPlainHeaders.setChecked(settings.print_plain_headers)

        self._update_mode_controls()
        self._update_sound_controls()
        self._update_print_controls()

    def to_settings(self) -> SendReceiveSettings:
        """
        Collect current UI contents into a SendReceiveSettings instance.
        """
        if self.rbEveryN.isChecked():
            mode = AutomationMode.EVERY_N_MINUTES
        elif self.rbSlots.isChecked():
            mode = AutomationMode.SLOT_TIMES
        else:
            mode = AutomationMode.MANUAL

        interval = max(1, int(self.spinInterval.value()))

        # Parse slots
        raw_slots = self.edSlots.text().replace(";", ",")
        slot_minutes: List[int] = []
        if raw_slots.strip():
            for part in raw_slots.split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    val = int(part)
                except ValueError:
                    continue
                if 0 <= val <= 59 and val not in slot_minutes:
                    slot_minutes.append(val)
            slot_minutes.sort()

        # When receiving
        play_sound = self.chkPlaySound.isChecked()
        sound_path = self.edSoundPath.text().strip()

        # Printing
        print_received = self.chkPrintReceived.isChecked()
        prx_copies = int(self.spinPrintReceived.value())

        print_sent = self.chkPrintSent.isChecked()
        psx_copies = int(self.spinPrintSent.value())

        print_receipts = self.chkPrintReceipts.isChecked()
        print_plain_headers = self.chkPrintPlainHeaders.isChecked()

        return SendReceiveSettings(
            mode=mode,
            interval_minutes=interval,
            slot_minutes=slot_minutes,
            play_sound_on_receive=play_sound,
            sound_file_path=sound_path,
            print_received=print_received,
            print_received_copies=prx_copies,
            print_sent=print_sent,
            print_sent_copies=psx_copies,
            print_receipts=print_receipts,
            print_plain_headers=print_plain_headers,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_mode_toggled(self, _checked: bool) -> None:
        self._update_mode_controls()
        self._on_changed()

    def _update_mode_controls(self) -> None:
        every = self.rbEveryN.isChecked()
        slots = self.rbSlots.isChecked()

        self.spinInterval.setEnabled(every)
        self.edSlots.setEnabled(slots)

    def _on_sound_toggled(self, _checked: bool) -> None:
        self._update_sound_controls()
        self._on_changed()

    def _update_sound_controls(self) -> None:
        enabled = self.chkPlaySound.isChecked()
        self.edSoundPath.setEnabled(enabled)
        self.btnBrowseSound.setEnabled(enabled)
        self.btnTestSound.setEnabled(enabled)
        self.btnTestSound.setEnabled(
            self.chkPlaySound.isChecked() and bool(self.edSoundPath.text().strip())
        )

    def _on_print_toggled(self, _checked: bool) -> None:
        self._update_print_controls()
        self._on_changed()

    def _update_print_controls(self) -> None:
        self.spinPrintReceived.setEnabled(self.chkPrintReceived.isChecked())
        self.spinPrintSent.setEnabled(self.chkPrintSent.isChecked())

    def _on_browse_sound(self) -> None:
        dlg = QtWidgets.QFileDialog(self)
        dlg.setWindowTitle("Select sound file")
        dlg.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dlg.setNameFilter("Sound files (*.wav *.mp3 *.ogg);;All files (*.*)")
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                self.edSoundPath.setText(files[0])

                # keep UI state in sync
                self._update_sound_controls()
                self._on_changed()

                # 🎯 UX polish: auto-play selected sound
                self._on_test_sound()


    def _on_test_sound(self) -> None:
        """
        Play the currently selected sound file so the user can preview it.

        Behavior:
        - Uses QSoundEffect (same as MainWindow receive alert)
        - Does not persist anything
        - Safe if file missing or invalid
        """
        path = self.edSoundPath.text().strip()

        if not path:
            QtWidgets.QMessageBox.information(
                self,
                "Test Sound",
                "No sound file selected.",
            )
            return

        url = QUrl.fromLocalFile(path)

        self._test_sound.stop()  # restart cleanly if already playing
        self._test_sound.setSource(url)
        self._test_sound.play()

    def _on_changed(self) -> None:
        self.changed.emit()

