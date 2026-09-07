# dialogs/form_entry_window.py

from __future__ import annotations

# import json   # #64, used for test only

from PySide6 import QtCore, QtGui, QtWidgets

from services.form_definition_loader import FormDefinition
from services.form_definition_loader import FormRegistry
from services.form_pdf_renderer import (            # #164
    FormPdfError,
    render_form_pdf,
)


class FormEntryWindow(QtWidgets.QDialog):
    """
    Generic OPXFORM data-entry window.

    Builds its UI entirely from FormDefinition.input["fields"].

    Step 4 responsibilities:
    - Create widgets from field type
    - Apply hints
    - Resolve simple system defaults
    - Validate required fields
    - Return a dictionary keyed by field "id"

    This class contains NO ICS-213-specific logic.
    """

    messageRequested = QtCore.Signal(object, object)    # #164

    def __init__(
        self,
        form: FormDefinition,
        values: dict[str, object] | None = None,
        read_only: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.form = form
        self._initial_values = values or {}
        self._read_only = read_only
        self._widgets: dict[str, QtWidgets.QWidget] = {}

        self.setWindowTitle(form.name)
        self.setMinimumWidth(650)
        self.resize(700, 700)

        self._build_ui()
        self._load_initial_values()
        self._apply_read_only()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        input_def = self.form.input
        title = str(input_def.get("title") or self.form.name)

        lbl_title = QtWidgets.QLabel(title)
        title_font = lbl_title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        lbl_title.setFont(title_font)
        root.addWidget(lbl_title)

        # --------------------------------------------------------------
        # 164, 260827
        # Scrollable form field area
        # --------------------------------------------------------------
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        # Forms should scroll vertically as needed, but should continue
        # fitting themselves to the available window width.
        scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        form_widget = QtWidgets.QWidget()

        form_layout = QtWidgets.QFormLayout(form_widget)
        form_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form_layout.setVerticalSpacing(8)

        fields = input_def.get("fields", []) or []

        for field in fields:
            field_type = str(field.get("type", "text")).strip().lower()

            # ----------------------------------------------------------
            # 164, 260827
            # Presentation-only section heading
            # ----------------------------------------------------------
            if field_type == "section":
                section_text = str(field.get("label", "") or "").strip()

                if section_text:
                    section_widget = QtWidgets.QWidget()
                    section_layout = QtWidgets.QVBoxLayout(section_widget)
                    section_layout.setContentsMargins(0, 6, 0, 2)
                    section_layout.setSpacing(2)

                    # Add separator except above the first section.
                    if form_layout.rowCount() > 0:
                        line = QtWidgets.QFrame()
                        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
                        section_layout.addWidget(line)

                    section_label = QtWidgets.QLabel(section_text)

                    font = section_label.font()
                    font.setBold(True)
                    font.setPointSize(font.pointSize() + 1)
                    section_label.setFont(font)

                    section_layout.addWidget(section_label)

                    form_layout.addRow(section_widget)

                continue


            # ----------------------------------------------------------
            # Normal data-entry field
            # ----------------------------------------------------------
            field_id = str(field.get("id", "")).strip()
            if not field_id:
                continue

            widget = self._create_widget(field)

            self._widgets[field_id] = widget

            label_text = self._field_label(field)

            if bool(field.get("required", False)):
                label_text += " *"

            form_layout.addRow(label_text + ":", widget)


        scroll.setWidget(form_widget)

        # Give the scroll area all remaining expandable vertical space.
        root.addWidget(scroll, 1)

        root.addSpacing(8)

        note = QtWidgets.QLabel("* Required field")
        note.setStyleSheet("font-style: italic;")
        root.addWidget(note)

        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)

        self.btnReload = QtWidgets.QPushButton("Reload Definition")
        self.btnPdf = QtWidgets.QPushButton("Show in PDF")  # #164
        self.btnCreate = QtWidgets.QPushButton("Create Message")
        self.btnClose = QtWidgets.QPushButton("Close")

        # PDF rendering is optional. Forms such as NTS may have no
        # PDF representation at all.
        self.btnPdf.setVisible(self.form.supports_pdf)

        buttons.addWidget(self.btnReload)                   # #164
        buttons.addWidget(self.btnPdf)                      # #164
        buttons.addWidget(self.btnCreate)
        buttons.addWidget(self.btnClose)

        root.addLayout(buttons)

        self.btnReload.clicked.connect(self._on_reload_definition)
        self.btnPdf.clicked.connect(self._on_show_pdf)      # #164
        self.btnCreate.clicked.connect(self._on_create)
        self.btnClose.clicked.connect(self.reject)


    def _load_initial_values(self) -> None:
        """
        Populate the generated widgets with existing OPXFORM values.

        Used when repatriating a received form.
        """
        for field_id, value in self._initial_values.items():
            widget = self._widgets.get(field_id)

            if widget is None:
                continue

            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setText(
                    "" if value is None else str(value)
                )

            elif isinstance(widget, QtWidgets.QPlainTextEdit):
                widget.setPlainText(
                    "" if value is None else str(value)
                )

            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(bool(value))

            elif isinstance(widget, QtWidgets.QDateEdit):
                text = "" if value is None else str(value)

                locale = QtCore.QLocale.system()

                date = locale.toDate(
                    text,
                    QtCore.QLocale.FormatType.ShortFormat,
                )

                if date.isValid():
                    widget.setDate(date)

            elif isinstance(widget, QtWidgets.QTimeEdit):
                text = "" if value is None else str(value)

                # Current wire representation is HHmm.
                time = QtCore.QTime.fromString(text, "HHmm")

                # Be forgiving if a future form sends HH:mm.
                if not time.isValid():
                    time = QtCore.QTime.fromString(text, "HH:mm")

                if time.isValid():
                    widget.setTime(time)


    def _apply_read_only(self) -> None:
        """
        Change the generic Form Entry window into a received-form viewer.
        """
        if not self._read_only:
            return

        for widget in self._widgets.values():

            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setReadOnly(True)

            elif isinstance(widget, QtWidgets.QPlainTextEdit):
                widget.setReadOnly(True)

            elif isinstance(widget, QtWidgets.QDateEdit):
                widget.setReadOnly(True)
                widget.setButtonSymbols(
                    QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons
                )

            elif isinstance(widget, QtWidgets.QTimeEdit):
                widget.setReadOnly(True)
                widget.setButtonSymbols(
                    QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons
                )

            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.setEnabled(False)

        # Received forms cannot create another packet message.
        self.btnCreate.setVisible(False)

        self.btnClose.setText("Close")


    def _field_label(self, field: dict) -> str:
        """
        Determine the human-facing input label.

        Preferred:
            label
            wire_label
            id
        """
        return str(
            field.get("label")
            or field.get("wire_label")
            or field.get("id")
            or ""
        ).strip()


    # ------------------------------------------------------------------
    # Widget factory
    # ------------------------------------------------------------------
    def _create_widget(self, field: dict) -> QtWidgets.QWidget:
        field_type = str(field.get("type", "text")).strip().lower()
        hint = str(field.get("hint", "") or "")
        default = field.get("default")

        if field_type == "text":
            widget = QtWidgets.QLineEdit()

            if hint:
                widget.setPlaceholderText(hint)

            if default is not None:
                widget.setText(self._resolve_default(default))

            return widget


        if field_type == "multiline":
            widget = QtWidgets.QPlainTextEdit()

            if hint:
                widget.setPlaceholderText(hint)

            rows = field.get("rows", 5)

            try:
                rows = max(2, int(rows))
            except (TypeError, ValueError):
                rows = 5

            metrics = widget.fontMetrics()
            widget.setMinimumHeight(
                metrics.lineSpacing() * rows + 20
            )

            if default is not None:
                widget.setPlainText(self._resolve_default(default))

            return widget


        if field_type == "date":
            widget = QtWidgets.QDateEdit()
            widget.setCalendarPopup(True)

            if default == "$CURRENT_DATE":
                widget.setDate(QtCore.QDate.currentDate())
            else:
                widget.setDate(QtCore.QDate.currentDate())

            # Let the operating-system locale control presentation.
            locale = QtCore.QLocale.system()
            widget.setDisplayFormat(
                locale.dateFormat(QtCore.QLocale.FormatType.ShortFormat)
            )

            return widget


        if field_type == "time":
            widget = QtWidgets.QTimeEdit()

            if default == "$CURRENT_TIME":
                widget.setTime(QtCore.QTime.currentTime())
            else:
                widget.setTime(QtCore.QTime.currentTime())

            # OPXFORM/EMCOMM convention: local 24-hour time.
            widget.setDisplayFormat("HH:mm")

            return widget


        if field_type == "checkbox":
            widget = QtWidgets.QCheckBox()

            if isinstance(default, bool):
                widget.setChecked(default)

            return widget


        # The loader should eventually prevent unsupported types,
        # but remain defensive here.
        raise ValueError(
            f"Unsupported OPXFORM field type: {field_type}"
        )


    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    def _resolve_default(self, value) -> str:
        """
        Resolve OPXFORM system-default tokens.

        Date/time widgets handle their tokens directly.
        Unknown tokens remain blank for now.
        """
        if value is None:
            return ""

        value = str(value)

        if value.startswith("$"):
            return ""

        return value


    # ------------------------------------------------------------------
    # Data extraction
    # ------------------------------------------------------------------
    def values(self) -> dict[str, object]:
        """
        Return current form contents keyed by OPXFORM field id.
        """
        result: dict[str, object] = {}

        fields = self.form.input.get("fields", []) or []

        for field in fields:
            field_id = str(field.get("id", "")).strip()

            if not field_id:
                continue

            widget = self._widgets.get(field_id)

            if widget is None:
                continue

            if isinstance(widget, QtWidgets.QLineEdit):
                value = widget.text().strip()

            elif isinstance(widget, QtWidgets.QPlainTextEdit):
                value = widget.toPlainText().strip()

            elif isinstance(widget, QtWidgets.QDateEdit):
                # Store what the operator sees.
                locale = QtCore.QLocale.system()
                value = locale.toString(
                    widget.date(),
                    QtCore.QLocale.FormatType.ShortFormat,
                )

            elif isinstance(widget, QtWidgets.QTimeEdit):
                # Compact 24-hour representation.
                value = widget.time().toString("HHmm")

            elif isinstance(widget, QtWidgets.QCheckBox):
                value = widget.isChecked()

            else:
                value = ""

            result[field_id] = value

        return result


    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_required(self) -> list[str]:
        missing: list[str] = []
        values = self.values()

        fields = self.form.input.get("fields", []) or []

        for field in fields:
            if not bool(field.get("required", False)):
                continue

            field_id = str(field.get("id", "")).strip()
            value = values.get(field_id)

            # False is a legitimate checkbox value.
            if isinstance(value, bool):
                continue

            if value is None or not str(value).strip():
                missing.append(self._field_label(field))

        return missing


    # ------------------------------------------------------------------
    # Step-4, -7B/C
    # ------------------------------------------------------------------
    def _on_reload_definition(self) -> None:
        """
        Reload this form's .opxform definition from disk while preserving
        the operator's current field values.
        """
        current_values = self.values()

        try:
            registry = FormRegistry(self.form.source_path.parent)
            registry.reload()

            reloaded = registry.get(self.form.form_id)

            if reloaded is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Reload Definition",
                    "The form definition could not be reloaded.\n\n"
                    f"Form ID: {self.form.form_id}",
                )
                return

            if reloaded.form_version != self.form.form_version:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Reload Definition",
                    "The form definition version has changed.\n\n"
                    f"Current version: {self.form.form_version}\n"
                    f"Reloaded version: {reloaded.form_version}",
                )
                return

        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Reload Definition",
                f"Unable to reload the form definition:\n\n{exc}",
            )
            return

        self.form = reloaded

        # Rebuild the generated form from the new definition.
        self._rebuild_form_ui(current_values)


    def _on_show_pdf(self) -> None:
        """
        Render the current form values onto the configured PDF template
        and open the resulting preview with the system PDF viewer.
        """

        # When composing a new form, don't preview an incomplete form.
        #
        # A received/repatriated form is allowed to contain incomplete
        # data, so read-only mode does not enforce current validation rules.
        if not self._read_only:
             missing = self._validate_required()

             if missing:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Required Fields",
                    "Please complete the following required fields:\n\n"
                    + "\n".join(f"• {name}" for name in missing),
                )
                return

        values = self.values()

        try:
            pdf_path = render_form_pdf(
                self.form,
                values,
            )

        except FormPdfError as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Show in PDF",
                str(exc),
            )
            return

        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Show in PDF",
                f"Unexpected error creating PDF preview:\n\n{exc}",
            )
            return

        opened = QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(
                str(pdf_path)
            )
        )

        if not opened:
            QtWidgets.QMessageBox.warning(
                self,
                "Show in PDF",
                "The PDF preview was created successfully, "
                "but OutpostX could not open it.\n\n"
                f"{pdf_path}",
            )


    def _on_create(self) -> None:
        missing = self._validate_required()

        if missing:
            QtWidgets.QMessageBox.warning(
                self,
                "Required Fields",
                "Please complete the following required fields:\n\n"
                + "\n".join(f"• {name}" for name in missing),
            )
            return

        values = self.values()

        self.messageRequested.emit(self.form, values)
        self.accept()

        # STEP 4 TEST ONLY:
        # Show exactly what the generic Forms Engine collected.
        ## dlg = QtWidgets.QMessageBox(self)
        ## dlg.setWindowTitle("OPXFORM Data")
        ## dlg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        ## dlg.setText("Form data collected successfully.")

        ## dlg.setDetailedText(
        ##     json.dumps(values, indent=2, ensure_ascii=False)
        ## )

        ## dlg.exec()

    def _rebuild_form_ui(
        self,
        values: dict[str, object],
    ) -> None:
        """
        Rebuild the FormEntryWindow using the current FormDefinition,
        preserving existing field values wherever field IDs still match.
        """
        old_layout = self.layout()

        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)

                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                    continue

                child_layout = item.layout()
                if child_layout is not None:
                    self._clear_layout(child_layout)

            QtWidgets.QWidget().setLayout(old_layout)

        self._widgets = {}
        self._initial_values = values

        self._build_ui()
        self._load_initial_values()
        self._apply_read_only()        


    def _clear_layout(
        self,
        layout: QtWidgets.QLayout,
    ) -> None:
        while layout.count():
            item = layout.takeAt(0)

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue

            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)