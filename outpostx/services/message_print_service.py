# services/message_print_service.py
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PySide6.QtPrintSupport import QPrinterInfo

# P139
from services.datetime_display import format_timestamp

@dataclass(frozen=True)
class PrintableMessage:
    title_call: str
    from_call: str = ""
    to_call: str = ""
    sent_at: str = ""
    subject: str = ""
    local_msg_id: str = ""
    body: str = ""


class MessagePrintService:
    """
    OutpostX message printing service.

    Rendering is print-only. It does not modify the stored/transmitted message.
    The body is rendered in monospace to preserve ASCII message formatting.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        self._parent = parent

    def _make_printer(self, printer_name: str = "") -> QPrinter:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
        printer.setPageMargins(
            QtCore.QMarginsF(0.5, 0.5, 0.5, 0.5),
            QPageLayout.Unit.Inch,
        )

        printer_name = (printer_name or "").strip()
        if printer_name:
            for info in QPrinterInfo.availablePrinters():
                if info.printerName() == printer_name:
                    printer.setPrinterName(printer_name)
                    break

        return printer


    def print_message(self, msg: PrintableMessage, *, include_headers: bool = True, printer_name: str = "") -> None:
        printer = self._make_printer(printer_name)

        dlg = QPrintDialog(printer, self._parent)
        dlg.setWindowTitle("Print Message")
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        doc = self._build_document(msg, include_headers=include_headers)
        doc.print_(printer)


    def print_message_silent(
        self,
        msg: PrintableMessage,
        *,
        include_headers: bool = True,
        printer_name: str = "",
        copies: int = 1,
    ) -> None:
        """
        Print a message without showing a print dialog.

        Intended for automation paths such as Auto-Print on receive.
        Uses the configured printer if provided, otherwise the system default.
        """
        copies = max(1, min(int(copies or 1), 9))

        printer = self._make_printer(printer_name)
        printer.setCopyCount(copies)

        doc = self._build_document(msg, include_headers=include_headers)
        doc.print_(printer)
        


    def preview_message(self, msg: PrintableMessage, *, include_headers: bool = True, printer_name: str = "") -> None:
        printer = self._make_printer(printer_name)

        dlg = QPrintPreviewDialog(printer, self._parent)
        dlg.setWindowTitle("Print Preview")

        def _render(p: QPrinter) -> None:
            doc = self._build_document(msg, include_headers=include_headers)
            doc.print_(p)

        dlg.paintRequested.connect(_render)
        dlg.exec()


    def _build_document(self, msg: PrintableMessage, *, include_headers: bool) -> QtGui.QTextDocument:
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(QtGui.QFont("Arial", 10))
        doc.setHtml(self._build_html(msg, include_headers=include_headers))
        return doc

    def _build_html(self, msg: PrintableMessage, *, include_headers: bool) -> str:
        title = html.escape((msg.title_call or "").strip())
        body = (msg.body or "").replace("\r\n", "\n").replace("\r", "\n").expandtabs(8)
        body_html = html.escape(body)

        header_rows = []
        if include_headers:
            self._add_header_row(header_rows, "From", msg.from_call)
            self._add_header_row(header_rows, "To", msg.to_call)
            self._add_header_row(header_rows, "Sent", self._format_sent_at(msg.sent_at))
            self._add_header_row(header_rows, "Subject", msg.subject)
            self._add_header_row(header_rows, "Local Msg ID", msg.local_msg_id)

        header_html = ""
        if header_rows:
            header_html = """
            <table class="headers">
              {}
            </table>
            """.format("\n".join(header_rows))

        return f"""
        <!doctype html>
        <html>
        <head>
        <style>
          body {{
            font-family: Arial, Helvetica, sans-serif;
            font-size: 10pt;
            color: #000;
          }}
          .title {{
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 4px;
          }}
            hr {{
                border: 0;
                border-top: 10px solid #000;  /* Increase this number (e.g., 5px, 8px, 10px) for more thickness */
                margin: 4px 0 14px 0;
                opacity: 1; /* Ensures the line is fully solid and dark */
            }}
          table.headers {{
            border-collapse: collapse;
            margin-bottom: 18px;
          }}
          table.headers td {{
            vertical-align: top;
            padding: 1px 10px 2px 0;
            font-size: 10pt;
          }}
          table.headers td.label {{
            font-weight: bold;
            white-space: nowrap;
          }}
          pre.body {{
            font-family: Consolas, "Courier New", monospace;
            font-size: 10pt;
            white-space: pre-wrap;
            margin-top: 0;
          }}
        </style>
        </head>
        <body>
          <div class="title">{title}</div>
          <hr>
          {header_html}
          <pre class="body">{body_html}</pre>
        </body>
        </html>
        """

    @staticmethod
    def _add_header_row(rows: list[str], label: str, value: str) -> None:
        value = (value or "").strip()
        if not value:
            return
        rows.append(
            "<tr>"
            f"<td class='label'>{html.escape(label)}:</td>"
            f"<td>{html.escape(value)}</td>"
            "</tr>"
        )

    @staticmethod
    def _format_sent_at(value: str) -> str:
        return format_timestamp(value, include_seconds=True).display    
