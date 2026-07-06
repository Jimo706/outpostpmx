"""
    Select a platform-appropriate monospace font for transcript and log views.

    This helper chooses the first available font from a prioritized list of
    common fixed-width fonts across major platforms (Windows, macOS, Linux),
    ensuring consistent alignment and predictable word-wrapping behavior.

    Rationale:
        - Packet and terminal-style transcripts benefit from fixed-width fonts
          (callsigns, message numbers, protocol output).
        - Some legacy or OEM bitmap fonts (e.g., 8514oem) are not supported by
          modern font backends such as DirectWrite and may trigger warnings.
        - Explicit font selection avoids Qt falling back to undesirable or
          platform-specific defaults.

    Selection strategy:
        1) Windows-preferred fonts (e.g., Consolas)
        2) macOS-preferred fonts (e.g., Menlo, Monaco)
        3) Linux-preferred fonts (e.g., DejaVu Sans Mono, Liberation Mono)
        4) Generic 'Monospace' fallback as a last resort

    Notes:
        - Qt does not provide automatic font-family fallback in the same way as
          CSS; therefore availability is checked explicitly using QFontInfo.
        - The returned QFont is suitable for read-only transcript/log widgets
          (QPlainTextEdit, QTextEdit) but is not intended to override user-
          configurable editor fonts.
        - Font size is specified in points and may be adjusted later via user
          preferences.

    Args:
        size: Point size for the selected font.

    Returns:
        A QFont instance using the first available monospace font.
"""
from PySide6.QtGui import QFont, QFontInfo

def pick_monospace_font(size: int = 10) -> QFont:
    candidates = [
        "Consolas",              # Windows
        "Menlo",                 # macOS
        "SF Mono",               # macOS (sometimes hidden)
        "Monaco",                # macOS (older)
        "DejaVu Sans Mono",      # Linux
        "Liberation Mono",       # Linux
        "Ubuntu Mono",           # Linux
        "Courier New",           # Last-resort fallback
    ]

    for name in candidates:
        f = QFont(name, size)
        if QFontInfo(f).family().lower() == name.lower():
            return f

    # Absolute fallback
    return QFont("Monospace", size)
