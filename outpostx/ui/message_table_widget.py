# ui/message_table_widget.py
from __future__ import annotations
from typing import Optional, List

from PySide6 import QtWidgets, QtCore, QtGui

from data.message_repo import MessageRepository
from .message_table_model import MessageTableModel


class MessageTableView(QtWidgets.QTableView):
    """
    Custom table view that starts drags containing OutpostX message IDs in a
    custom MIME type: 'application/x-outpostx-msgids'.

    FolderTreeWidget is already wired to accept this MIME and move messages
    between folders.
    """
    deletePressed = QtCore.Signal()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """
        Added to support the DEL message delete keypress
        """
        if event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            self.deletePressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


    def startDrag(self, supportedActions: QtCore.Qt.DropActions) -> None:
        model = self.model()
        sel_model = self.selectionModel()
        if model is None or sel_model is None:
            return

        indexes: List[QtCore.QModelIndex] = sel_model.selectedRows()
        if not indexes:
            return

        # Collect msgidx values from selected rows
        msg_ids: List[str] = []
        item_at = getattr(model, "item_at", None)

        for idx in indexes:
            row = idx.row()
            if callable(item_at):
                row_item = item_at(row)
                if not row_item or not getattr(row_item, "msg", None):
                    continue
                mid = getattr(row_item.msg, "msgidx", None)
            else:
                # Fallback: try reading from column 0, UserRole
                mid = model.data(model.index(row, 0), QtCore.Qt.ItemDataRole.UserRole)

            if mid is not None:
                try:
                    msg_ids.append(str(int(mid)))
                except (TypeError, ValueError):
                    continue

        if not msg_ids:
            return

        mime = QtCore.QMimeData()
        mime.setData(
            "application/x-outpostx-msgids",
            ",".join(msg_ids).encode("utf-8"),
        )

        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.exec(QtCore.Qt.DropAction.MoveAction)


class MessageTableWidget(QtWidgets.QWidget):
    """
    Composite widget: message table + preview pane.

    Responsibilities:
    - Display messages using MessageTableModel.
    - Provide a preview of the selected message body.
    - Emit signals for single/double-clicks with msgidx.
    - Context menu operations: open, mark read/unread, delete.
    - Deletion semantics:
        * In normal folders, Delete -> move to Trash.
        * In Trash, Delete -> permanent delete from DB.
    - Persist basic geometry (font size, column widths, splitter state).
    """

    messageSingleClicked = QtCore.Signal(int)
    messageDoubleClicked = QtCore.Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._repo: Optional[MessageRepository] = None
        self._settings: Optional[QtCore.QSettings] = None
        self._settings_prefix: Optional[str] = None

        # Track current folder and Trash folder
        self._current_folderidx: Optional[int] = None
        self._trash_folderidx: Optional[int] = None

        # Splitter: table (top) + preview (bottom)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, self)

        # Table view (custom subclass to implement drag)
        self.view = MessageTableView(self.splitter)
        self.view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setSortingEnabled(True)
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setSectionsClickable(True)
        self.view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)

        # supports Select rows → press DEL → move to Trash (or purge if already in Trash)
        self.view.deletePressed.connect(lambda: self._delete_msgidxs(self._selected_msgidxs()))

        # Enable drag-only from the table; drop is handled by FolderTreeWidget
        self.view.setDragEnabled(True)
        self.view.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)

        # Model
        self.model = MessageTableModel(repo=None, parent=self)
        self.view.setModel(self.model)

        # Preview pane
        self.preview = QtWidgets.QTextEdit(self.splitter)
        self.preview.setReadOnly(True)
        # 260429: Set preview for monospace font 
        preview_font = QtGui.QFont("Consolas", 10)
        preview_font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
        self.preview.setFont(preview_font)
        self.preview.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)

        # Layout
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.splitter)

        # Signals
        self.view.clicked.connect(self._on_single_click)
        self.view.doubleClicked.connect(self._on_double_click)
        self.view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.view.horizontalHeader().sectionDoubleClicked.connect(self._auto_fit_column)

        # Context menu
        self.view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_context_menu)

        # Default sort: Time column (7) descending, adjust if your model differs
        self.view.sortByColumn(7, QtCore.Qt.SortOrder.DescendingOrder)

        # Initial splitter ratio
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def setRepository(self, repo: MessageRepository) -> None:
        """
        Attach a MessageRepository to this widget and its model.
        Also caches the Trash folder index for deletion semantics.
        """
        self._repo = repo
        self.model._repo = repo

        # Cache Trash folder id (if helper exists)
        trash_idx = None
        helper = getattr(repo, "_root_folderidx_by_name", None)
        if callable(helper):
            trash_idx = helper("Trash")
        self._trash_folderidx = trash_idx

    def setFolder(self, folderidx: int) -> None:
        """
        Switch the view to a different folder.
        """
        self._current_folderidx = folderidx
        self.model.set_folder(folderidx)

        # Clear any old selection/preview when changing folders
        self.view.clearSelection()
        self.preview.clear()

        # Re-apply default sort after folder change
        self.view.sortByColumn(7, QtCore.Qt.SortOrder.DescendingOrder)

    def refresh(self) -> None:
        """
        Reload messages from the repository for the current folder.
        """
        self.model.refresh()

    # ------------------------------------------------------------------
    # Settings / geometry
    # ------------------------------------------------------------------
    def setSettings(self, settings: QtCore.QSettings, prefix: str = "MessageTable") -> None:
        self._settings = settings
        self._settings_prefix = prefix
        self.restoreGeometryState()

    def saveGeometryState(self) -> None:
        if not self._settings or not self._settings_prefix:
            return
        self._settings.beginGroup(self._settings_prefix)

        # Font size
        self._settings.setValue("font_size", self.view.font().pointSize())

        # Column widths
        widths = [self.view.columnWidth(c) for c in range(self.model.columnCount())]
        self._settings.setValue("col_widths", widths)

        # Splitter state
        self._settings.setValue("splitter", self.splitter.saveState())

        self._settings.endGroup()

    def restoreGeometryState(self) -> None:
        if not self._settings or not self._settings_prefix:
            return
        self._settings.beginGroup(self._settings_prefix)

        # 260429: Set preview for monospace font 
        size = self._settings.value("font_size", None, type=int)
        if size:
            # Message list/table font can remain normal/proportional.
            f = self.view.font()
            f.setPointSize(size)
            self.view.setFont(f)

            # Preview should remain monospace for ASCII formatting.
            pf = QtGui.QFont("Consolas", size)
            pf.setStyleHint(QtGui.QFont.StyleHint.Monospace)
            self.preview.setFont(pf)

        widths = self._settings.value("col_widths", [], type=list)
        if widths:
            for c, w in enumerate(widths):
                try:
                    self.view.setColumnWidth(c, int(w))
                except Exception:
                    pass

        s = self._settings.value("splitter", None)
        if s is not None:
            self.splitter.restoreState(s)

        self._settings.endGroup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _msgidx_from_index(self, index: QtCore.QModelIndex) -> Optional[int]:
        row_item = self.model.item_at(index.row())
        if not row_item or row_item.msg.msgidx is None:
            return None
        return int(row_item.msg.msgidx)

    def currentMessageIdx(self) -> Optional[int]:
        idx = self.view.currentIndex()
        if not idx.isValid():
            return None
        return self._msgidx_from_index(idx)


    def _selected_msgidxs(self) -> list[int]:
        """
        Return msgidx values for all selected rows (deduped, sorted by row order).
        """
        sel = self.view.selectionModel()
        if sel is None:
            return []

        indexes = sel.selectedRows()
        if not indexes:
            return []

        out: list[int] = []
        for idx in indexes:
            mid = self._msgidx_from_index(idx)
            if mid is not None:
                out.append(int(mid))

        # De-dupe while preserving order
        seen = set()
        uniq: list[int] = []
        for mid in out:
            if mid in seen:
                continue
            seen.add(mid)
            uniq.append(mid)
        return uniq


    def _delete_msgidxs(self, msgidxs: list[int]) -> None:
        """
        Two-step delete:
          - In normal folders: move selected to Trash
          - In Trash: permanently delete selected
        """
        if not self._repo or not msgidxs:
            return

        if self._in_trash_folder():
            # Permanent delete: mark + purge
            for mid in msgidxs:
                self._repo.soft_delete(mid)
            self._repo.purge_trash(msgidxs)
        else:
            # Soft delete: move to Trash
            for mid in msgidxs:
                self._repo.move_to_trash(mid)

        self.refresh()
        self.view.clearSelection()
        self.preview.clear()


    def increaseFont(self) -> None:
        """Increase font size for both table and preview."""
        f = self.view.font()
        f.setPointSize(f.pointSize() + 1)
        self.view.setFont(f)
        self.preview.setFont(f)

    def decreaseFont(self) -> None:
        """Decrease font size for both table and preview."""
        f = self.view.font()
        f.setPointSize(max(6, f.pointSize() - 1))
        self.view.setFont(f)
        self.preview.setFont(f)

    def _in_trash_folder(self) -> bool:
        """
        Return True if the currently displayed folder is the Trash root.
        """
        if self._current_folderidx is None or self._trash_folderidx is None:
            return False
        return self._current_folderidx == self._trash_folderidx

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_single_click(self, index: QtCore.QModelIndex) -> None:
        mid = self._msgidx_from_index(index)
        if mid is not None:
            self.messageSingleClicked.emit(mid)

    def _on_double_click(self, index: QtCore.QModelIndex) -> None:
        mid = self._msgidx_from_index(index)
        if mid is None or not self._repo:
            return
        # Opening marks as read
        self._repo.mark_read(mid, True)
        self.refresh()
        self.messageDoubleClicked.emit(mid)

    def _on_selection_changed(self, _sel, _desel) -> None:
        idx = self.view.currentIndex()
        if not idx.isValid():
            self.preview.clear()
            return
        row_item = self.model.item_at(idx.row())
        body_text = (row_item.body.message if (row_item and row_item.body) else "") or ""
        self.preview.setPlainText(body_text)

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        if not self._repo:
            return

        index = self.view.indexAt(pos)
        if not index.isValid():
            return
        mid = self._msgidx_from_index(index)
        if mid is None:
            return

        menu = QtWidgets.QMenu(self)
        act_open = menu.addAction("Open")
        act_read = menu.addAction("Mark as Read")
        act_unread = menu.addAction("Mark as Unread")
        menu.addSeparator()
        act_delete = menu.addAction("Delete")

        action = menu.exec(self.view.viewport().mapToGlobal(pos))
        if not action:
            return

        if action is act_open:
            self._on_double_click(index)
        elif action is act_read:
            self._repo.mark_read(mid, True)
            self.refresh()
        elif action is act_unread:
            self._repo.mark_read(mid, False)
            self.refresh()

        elif action is act_delete:
            # If user right-clicked a row that isn't in the selection,
            # make that row the (single) selection before deleting.
            if not self.view.selectionModel().isSelected(index):
                self.view.clearSelection()
                self.view.selectRow(index.row())

            msgidxs = self._selected_msgidxs()
            self._delete_msgidxs(msgidxs)

        """
        elif action is act_delete:
            # Two-step delete:
            # - In normal folders → move to Trash
            # - In Trash → permanently remove
            if self._in_trash_folder():
                self._repo.soft_delete(mid)
                self._repo.purge_trash([mid])
            else:
                self._repo.move_to_trash(mid)

            # Refresh view and clear selection/preview since the prior row is gone
            self.refresh()
            self.view.clearSelection()
            self.preview.clear()
        """
    def _auto_fit_column(self, section: int) -> None:
        self.view.resizeColumnToContents(section)

    # ------------------------------------------------------------------
    # Persistence hook
    # ------------------------------------------------------------------
    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        self.saveGeometryState()
        super().closeEvent(e)
