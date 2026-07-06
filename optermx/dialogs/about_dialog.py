# dialogs/about_dialog.py

"""
About dialog for OpTermX.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
)
from services.app_paths import AppPaths


class AboutDialog(QDialog):
    """
    Simple About dialog for OpTermX.
    """

    def __init__(self, title: str, version: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"About {title}")
        self.setWindowIcon(QIcon(AppPaths.resource_path("polar3232.ico")))

        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # ------------------------------------------------------------
        # Title
        # ------------------------------------------------------------
        lbl_title = QLabel(f"{title}")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        lbl_title.setFont(font)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(lbl_title)

        # ------------------------------------------------------------
        # Version
        # ------------------------------------------------------------
        lbl_version = QLabel(f"Version {version}")
        lbl_version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(lbl_version)

        # ------------------------------------------------------------
        # Description
        # ------------------------------------------------------------
        lbl_desc = QLabel(
            "Multi-interface stand-alone terminal emulator for Amateur "
            "Packet Radio, manual BBS access, and network operations."
        )

        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lbl_desc.setWordWrap(True)

        layout.addWidget(lbl_desc)

        # ------------------------------------------------------------
        # Capability Columns
        # ------------------------------------------------------------
        columns_layout = QHBoxLayout()

        # Left column
        lbl_interfaces = QLabel(
            "<b>Supported Interfaces</b><br>"
            "• Serial<br>"
            "• Telnet/TCP<br>"
            "• AGWPE<br>"
            "• SSH"
        )

        lbl_interfaces.setTextFormat(Qt.TextFormat.RichText)

        # Right column
        lbl_platforms = QLabel(
            "<b>Supported Platforms</b><br>"
            "• Windows<br>"
            "• Linux<br>"
            "• macOS<br>"
        )

        lbl_platforms.setTextFormat(Qt.TextFormat.RichText)

        columns_layout.addStretch()
        columns_layout.addWidget(lbl_interfaces)
        columns_layout.addSpacing(40)
        columns_layout.addWidget(lbl_platforms)
        columns_layout.addStretch()

        layout.addLayout(columns_layout)

        # ------------------------------------------------------------
        # Footer
        # ------------------------------------------------------------
        lbl_footer = QLabel(
            "Built with Python and PySide6.\n"
            "© 2026 Jim Oberhofer KN6PE"
        )

        lbl_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(lbl_footer)

        # ------------------------------------------------------------
        # OK button
        # ------------------------------------------------------------
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)

        button_layout.addWidget(btn_ok)

        layout.addStretch()
        layout.addLayout(button_layout)