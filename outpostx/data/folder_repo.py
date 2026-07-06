# data/folder_repo.py
"""
Folder repository (folders table).

This module provides a lightweight persistence helper for the folder tree stored in
the SQLite `folders` table. It intentionally focuses on *structure* (folder rows,
parent/child relationships) and a small set of convenience queries used by the UI.

Architectural role:
- Closer to a DAO than a workflow repository: contains SQL and simple CRUD.
- Does *not* encode folder semantics like Inbox/Outbox/Drafts; that belongs in higher
  layers (MainWindow bootstrap / MessageRepository / SqliteMessageService).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import sqlite3
from pathlib import Path

@dataclass
class Folder:
    folderidx: int
    name: str
    parentidx: Optional[int]

class FolderRepo:
    """Lightweight SQLite-backed repository for the `folders` table.

    Responsibilities:
      - CRUD operations on folder rows
      - Query helpers for folder tree navigation (roots/children)
      - Minimal message-related helper (count and bulk move)

    Non-responsibilities:
      - Does not enforce special root folder meaning (Inbox/Outbox/Drafts/etc.)
      - Does not enforce message lifecycle rules (see MessageRepository / SqliteMessageService)
    """
    def __init__(self, db_path: Path | str):
        self._db = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ---- queries ----
    def get_all(self) -> List[Folder]:
        sql = "SELECT folderidx, name, parentidx FROM folders ORDER BY name COLLATE NOCASE"
        with self._connect() as c:
            rows = c.execute(sql).fetchall()
            return [Folder(r["folderidx"], r["name"], r["parentidx"]) for r in rows]

    def get_children(self, parentidx: Optional[int]) -> List[Folder]:
        if parentidx is None:
            sql = "SELECT folderidx, name, parentidx FROM folders WHERE parentidx IS NULL ORDER BY name COLLATE NOCASE"
            params = ()
        else:
            sql = "SELECT folderidx, name, parentidx FROM folders WHERE parentidx=? ORDER BY name COLLATE NOCASE"
            params = (parentidx,)
        with self._connect() as c:
            rows = c.execute(sql, params).fetchall()
            return [Folder(r["folderidx"], r["name"], r["parentidx"]) for r in rows]

    def create(self, name: str, parentidx: Optional[int]) -> int:
        with self._connect() as c:
            cur = c.execute("INSERT INTO folders(name, parentidx) VALUES(?, ?)", (name, parentidx))
            c.commit()
            return cur.lastrowid

    def rename(self, folderidx: int, new_name: str) -> int:
        with self._connect() as c:
            cur = c.execute("UPDATE folders SET name=? WHERE folderidx=?", (new_name, folderidx))
            c.commit()
            return cur.rowcount

    def has_children(self, folderidx: int) -> bool:
        with self._connect() as c:
            r = c.execute("SELECT 1 FROM folders WHERE parentidx=? LIMIT 1", (folderidx,)).fetchone()
            return bool(r)

    def message_count(self, folderidx: int) -> int:
        with self._connect() as c:
            r = c.execute("SELECT COUNT(*) AS c FROM messages WHERE folderidx=?", (folderidx,)).fetchone()
            return int(r["c"] if r else 0)

    def delete(self, folderidx: int) -> int:
        """Delete folder (assumes already emptied & no children)."""
        with self._connect() as c:
            cur = c.execute("DELETE FROM folders WHERE folderidx=?", (folderidx,))
            c.commit()
            return cur.rowcount

    def move_messages_to_folder(self, msgidxs: List[int], dest_folderidx: int) -> int:
        if not msgidxs:
            return 0
        ph = ",".join("?" for _ in msgidxs)
        sql = f"UPDATE messages SET folderidx=? WHERE msgidx IN ({ph})"
        with self._connect() as c:
            cur = c.execute(sql, (dest_folderidx, *msgidxs))
            c.commit()
            return cur.rowcount
