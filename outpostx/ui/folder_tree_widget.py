# ui/folder_tree_widget.py  (PySide6 version, with fixed drag/drop)
from __future__ import annotations
from typing import Optional, Dict, Set, List

from PySide6 import QtCore, QtGui, QtWidgets

from data.folder_repo import FolderRepo, Folder

SYSTEM_ROOT_ORDER = ("Inbox", "Outbox", "Drafts", "Sent", "Trash")

#TODO: let subdirectories to be added to root directories
#TODO: Always open the program pointing to the Intray

class FolderTreeView(QtWidgets.QTreeView):
    """
    QTreeView that accepts drops from the message table.

    It understands the custom MIME type "application/x-outpostx-msgids" and
    emits a signal with (msgidxs, dest_folderidx) when a drop is accepted.
    """

    messagesDropped = QtCore.Signal(list, int)  # (msgidxs, dest_folderidx)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)

    def dragEnterEvent(self, e: QtGui.QDragEnterEvent) -> None:
        if e.mimeData().hasFormat("application/x-outpostx-msgids"):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e: QtGui.QDragMoveEvent) -> None:
        if e.mimeData().hasFormat("application/x-outpostx-msgids"):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent) -> None:
        if not e.mimeData().hasFormat("application/x-outpostx-msgids"):
            e.ignore()
            return

        # Qt6: use position(), not pos()
        idx = self.indexAt(e.position().toPoint())
        if not idx.isValid():
            e.ignore()
            return

        model = self.model()
        if model is None:
            e.ignore()
            return

        item = model.itemFromIndex(idx)
        if item is None:
            e.ignore()
            return

        dest = int(item.data(QtCore.Qt.ItemDataRole.UserRole))

        raw = e.mimeData().data("application/x-outpostx-msgids")
        try:
            text = bytes(raw).decode("utf-8")
        except Exception:
            e.ignore()
            return

        msgidxs = [int(s) for s in text.split(",") if s.strip().isdigit()]
        if not msgidxs:
            e.ignore()
            return

        # Let the parent widget decide what to do with these
        self.messagesDropped.emit(msgidxs, dest)
        e.acceptProposedAction()


class FolderTreeWidget(QtWidgets.QWidget):
    folderSelected = QtCore.Signal(int)               # emits folderidx
    moveMessagesRequested = QtCore.Signal(list, int)  # (msgidxs, dest_folderidx)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._repo: Optional[FolderRepo] = None
        self._settings: Optional[QtCore.QSettings] = None
        self._settings_prefix = "FolderTree"
        self._trash_names: Set[str] = {"Trash", "Recycle Bin"}
        self._trash_id: Optional[int] = None
        # System root folders (Inbox, Outbox, Drafts, Sent, Trash)
        self._system_root_names: Set[str] = set(SYSTEM_ROOT_ORDER)

        self.view = FolderTreeView(self)
        self.view.setHeaderHidden(True)
        self.view.setAnimated(True)
        self.view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.view.setUniformRowHeights(True)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self.model = QtGui.QStandardItemModel(self)
        self.view.setModel(self.model)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)

        # signals
        self.view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_context_menu)
        self.view.messagesDropped.connect(self._on_messages_dropped)

    # ---- wiring ----
    def setRepository(self, repo: FolderRepo):
        self._repo = repo

    def setSettings(self, settings: QtCore.QSettings, prefix: str = "FolderTree"):
        self._settings = settings
        self._settings_prefix = prefix

    # ---- build tree ----
    def refresh(self):
        if not self._repo:
            return
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Folders"])

        style = self.style()
        dir_icon = style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
        trash_icon = style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TrashIcon)

        id_to_item: Dict[int, QtGui.QStandardItem] = {}

        roots = self._repo.get_children(None)

        # Group by name so duplicates (if any) stay together
        by_name: Dict[str, List[Folder]] = {}
        for f in roots:
            by_name.setdefault(f.name, []).append(f)

        ordered_roots: List[Folder] = []

        # 1) System roots in fixed order
        for sys_name in SYSTEM_ROOT_ORDER:
            if sys_name in by_name:
                ordered_roots.extend(by_name.pop(sys_name))

        # 2) Remaining roots, sorted alpha by name
        for name in sorted(by_name.keys(), key=str.casefold):
            ordered_roots.extend(by_name[name])

        for f in ordered_roots:
            item = QtGui.QStandardItem(dir_icon, f.name)
            item.setData(int(f.folderidx), QtCore.Qt.ItemDataRole.UserRole)
            item.setDropEnabled(True)
            self.model.appendRow(item)
            id_to_item[f.folderidx] = item
            if f.name in self._trash_names:
                item.setIcon(trash_icon)
                self._trash_id = f.folderidx
            self._populate_children(item, f.folderidx, id_to_item, dir_icon, trash_icon)

        # Restore expansion + selection
        self._restore_state()

        # Ensure something is selected
        if not self.view.currentIndex().isValid() and self.model.rowCount() > 0:
            first = self.model.index(0, 0)
            self.view.setCurrentIndex(first)

    def _populate_children(
        self,
        parent_item: QtGui.QStandardItem,
        parentidx: int,
        id_to_item: Dict[int, QtGui.QStandardItem],
        dir_icon: QtGui.QIcon,
        trash_icon: QtGui.QIcon,
    ):
        assert self._repo is not None
        for f in self._repo.get_children(parentidx):
            item = QtGui.QStandardItem(dir_icon, f.name)
            item.setData(int(f.folderidx), QtCore.Qt.ItemDataRole.UserRole)
            item.setDropEnabled(True)
            if f.name in self._trash_names:
                item.setIcon(trash_icon)
                self._trash_id = f.folderidx
            parent_item.appendRow(item)
            id_to_item[f.folderidx] = item
            self._populate_children(item, f.folderidx, id_to_item, dir_icon, trash_icon)

    # ---- selection ----
    def _on_selection_changed(self, *_):
        idx = self.view.currentIndex()
        if not idx.isValid():
            return
        folderidx = self.model.itemFromIndex(idx).data(QtCore.Qt.ItemDataRole.UserRole)
        if folderidx is not None:
            self.folderSelected.emit(int(folderidx))

    # ---- context menu ----
    def _on_context_menu(self, pos: QtCore.QPoint):
        idx = self.view.indexAt(pos)

        # handle adding new root folder
        if not idx.isValid():
            menu = QtWidgets.QMenu(self)
            act_add_root = menu.addAction("Add root folder…")
            chosen = menu.exec(self.view.viewport().mapToGlobal(pos))
            if chosen is act_add_root:
                name, ok = QtWidgets.QInputDialog.getText(self, "New root folder", "Folder name:")
                if ok and name.strip():
                    self._repo.create(name.strip(), None)
                    self.refresh()
            return

        item = self.model.itemFromIndex(idx)
        folderidx = int(item.data(QtCore.Qt.ItemDataRole.UserRole))

        parent_item = item.parent()
        is_root = parent_item is None
        is_system_root = is_root and item.text() in self._system_root_names

        menu = QtWidgets.QMenu(self)
        act_add = menu.addAction("Add folder…")
        act_rename = menu.addAction("Rename…")
        act_delete = menu.addAction("Delete…")

        # System roots: cannot rename or delete
        if is_system_root:
            act_rename.setEnabled(False)
            act_delete.setEnabled(False)
        # Trash-like roots: still protect delete even if not in system list
        elif self._trash_id is not None and folderidx == self._trash_id:
            act_delete.setEnabled(False)

        chosen = menu.exec(self.view.viewport().mapToGlobal(pos))
        if not chosen:
            return

        if chosen is act_add:
            name, ok = QtWidgets.QInputDialog.getText(self, "New folder", "Folder name:")
            if ok and name.strip():
                self._repo.create(name.strip(), folderidx)
                self.refresh()

        elif chosen is act_rename:
            name, ok = QtWidgets.QInputDialog.getText(
                self,
                "Rename folder",
                "New name:",
                text=item.text(),
            )
            if ok and name.strip():
                self._repo.rename(folderidx, name.strip())
                self.refresh()

        elif chosen is act_delete:
            if self._repo.has_children(folderidx):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Delete folder",
                    "This folder has subfolders. Remove them first.",
                )
                return
            mc = self._repo.message_count(folderidx)
            if mc > 0:
                btn = QtWidgets.QMessageBox.question(
                    self,
                    "Delete folder",
                    f"This folder contains {mc} message(s).\n\nMove them to Trash?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No
                    | QtWidgets.QMessageBox.StandardButton.Cancel,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )
                if btn == QtWidgets.QMessageBox.StandardButton.Cancel:
                    return
                if btn == QtWidgets.QMessageBox.StandardButton.Yes:
                    if self._trash_id is None:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Delete folder",
                            "No Trash folder found.",
                        )
                        return
                    msgids = self._collect_msgids(folderidx)
                    self._repo.move_messages_to_folder(msgids, self._trash_id)
                else:
                    return
            self._repo.delete(folderidx)
            self.refresh()

    # ---- drag/drop from message table ----
    def _on_messages_dropped(self, msgidxs: List[int], dest_folderidx: int) -> None:
        """
        Handle a drop reported by FolderTreeView: move messages and notify listeners.
        """
        if not self._repo:
            return
        moved = self._repo.move_messages_to_folder(msgidxs, dest_folderidx)
        if moved:
            self.moveMessagesRequested.emit(msgidxs, dest_folderidx)

    # ---- helper to collect message ids for a folder (and descendants) ----
    def _collect_msgids(self, folderidx: int) -> List[int]:
        """Ask repo to return all message ids in this folder subtree."""
        return self._repo.messages_in_subtree(folderidx)

    # ---- state persistence ----
    def saveState(self):
        if not self._settings:
            return
        self._settings.beginGroup(self._settings_prefix)
        # expanded ids
        expanded: List[int] = []

        def walk(idx: QtCore.QModelIndex):
            for r in range(self.model.rowCount(idx)):
                cidx = self.model.index(r, 0, idx)
                if self.view.isExpanded(cidx):
                    item = self.model.itemFromIndex(cidx)
                    expanded.append(int(item.data(QtCore.Qt.ItemDataRole.UserRole)))
                walk(cidx)

        walk(QtCore.QModelIndex())
        self._settings.setValue("expanded_ids", expanded)
        # selected id
        cur = self.view.currentIndex()
        selected = None
        if cur.isValid():
            selected = int(self.model.itemFromIndex(cur).data(QtCore.Qt.ItemDataRole.UserRole))
        self._settings.setValue("selected_id", selected if selected is not None else -1)
        self._settings.endGroup()

    def _restore_state(self):
        if not self._settings:
            return
        self._settings.beginGroup(self._settings_prefix)
        expanded = self._settings.value("expanded_ids", [], type=list)
        selected = self._settings.value("selected_id", -1, type=int)

        # expand
        def expand_match(idx: QtCore.QModelIndex):
            for r in range(self.model.rowCount(idx)):
                cidx = self.model.index(r, 0, idx)
                item = self.model.itemFromIndex(cidx)
                fid = int(item.data(QtCore.Qt.ItemDataRole.UserRole))
                if fid in expanded:
                    self.view.setExpanded(cidx, True)
                expand_match(cidx)

        expand_match(QtCore.QModelIndex())

        # select
        if selected != -1:
            self._select_by_id(selected)
        self._settings.endGroup()

    def _select_by_id(self, folderidx: int) -> bool:
        def walk(idx: QtCore.QModelIndex) -> Optional[QtCore.QModelIndex]:
            for r in range(self.model.rowCount(idx)):
                cidx = self.model.index(r, 0, idx)
                item = self.model.itemFromIndex(cidx)
                fid = int(item.data(QtCore.Qt.ItemDataRole.UserRole))
                if fid == folderidx:
                    return cidx
                got = walk(cidx)
                if got:
                    return got
            return None

        tgt = walk(QtCore.QModelIndex())
        if tgt:
            self.view.setCurrentIndex(tgt)
            return True
        return False

    def closeEvent(self, e: QtGui.QCloseEvent):
        self.saveState()
        super().closeEvent(e)

    # ---------------------
    # helpers
    # ---------------------
    def current_folderidx(self) -> Optional[int]:
        """
        Return the folderidx of the currently selected folder, or None
        if nothing is selected.
        """
        idx = self.view.currentIndex()
        if not idx.isValid():
            return None
        item = self.model.itemFromIndex(idx)
        if item is None:
            return None
        val = item.data(QtCore.Qt.ItemDataRole.UserRole)
        return int(val) if val is not None else None