# outpostx3/data/schema_bootstrap.py
"""
SQLite schema bootstrap helpers.

This module contains small, idempotent helpers that ensure required database
tables and views exist when OutpostX starts on a fresh database file.

Why this exists:
- Several parts of the app (folders, messages, v_messages_full) assume tables exist.
- On first run (or after deleting outpostx.db), those tables are missing.
- These helpers create the minimal schema needed for the UI and services to run.

Design notes:
- Functions are intentionally *idempotent* (safe to call repeatedly).
- The helpers accept either:
    * a Path-like db_path, or
    * an object that exposes a private _connect() method (currently MessageDAO).
  This allows early bootstrap without importing higher layers.

This module does not attempt to manage full migrations. It only creates the
baseline schema and recreates the v_messages_full view to reflect code changes.
"""
from __future__ import annotations
import sqlite3
from typing import Iterable, Tuple

def _connect_path(db_path) -> sqlite3.Connection:
    """
    Open a SQLite connection from either a DAO-like object or a filesystem path.

    Args:
        db_path: Either a Path/str pointing to the SQLite file, or an object
            exposing a private _connect() method (e.g., MessageDAO).

    Returns:
        A sqlite3.Connection configured with Row mapping and foreign keys.
    """
    # Support both MessageDAO and a raw Path
    if hasattr(db_path, "_connect"):
        return db_path._connect()  # MessageDAO
    import sqlite3  # fallback
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_folders_table_and_roots(dao_or_path) -> None:
    """
    Ensure the `folders` table exists and seed required root folders.

    Creates the table if needed and ensures the root folders exist:
      - Inbox
      - Outbox
      - Trash

    This function is safe to call multiple times.
    """
    with _connect_path(dao_or_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                folderidx   INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                parentidx   INTEGER REFERENCES folders(folderidx)
                              ON UPDATE CASCADE ON DELETE RESTRICT,
                UNIQUE(name, parentidx)
            );
        """)
        for name in ("Inbox", "Outbox", "Trash"):
            conn.execute("""
                INSERT INTO folders (name, parentidx)
                SELECT ?, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM folders WHERE name=? AND parentidx IS NULL
                )
            """, (name, name))
        conn.commit()

def ensure_message_schema_and_view(dao_or_path) -> None:
    """
    Ensure message tables and the v_messages_full view exist.

    Creates:
      - messages
      - message_bodies
    And recreates (DROP + CREATE):
      - v_messages_full

    Recreating the view ensures column changes are reflected without requiring
    manual schema maintenance.
    """
    with _connect_path(dao_or_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                msgidx        INTEGER PRIMARY KEY AUTOINCREMENT,
                bbs_call      TEXT,
                bbsmsgno      TEXT,
                from_call     TEXT,
                to_call       TEXT,
                subject       TEXT,
                messagelen    INTEGER DEFAULT 0,
                sent_at       TEXT,
                rcvd_at       TEXT,
                mstate        TEXT NOT NULL,
                direction     TEXT NOT NULL,
                is_read       INTEGER NOT NULL DEFAULT 0,
                is_deleted    INTEGER NOT NULL DEFAULT 0,
                is_urgent     INTEGER NOT NULL DEFAULT 0,
                is_encoded    INTEGER NOT NULL DEFAULT 0,
                is_locked     INTEGER NOT NULL DEFAULT 0,
                is_msgdelreq  INTEGER NOT NULL DEFAULT 0,
                has_attachment INTEGER NOT NULL DEFAULT 0,
                header        TEXT,
                folderidx     INTEGER NOT NULL REFERENCES folders(folderidx)
                                  ON UPDATE CASCADE ON DELETE RESTRICT,
                mtype         INTEGER NOT NULL DEFAULT 0,
                messageid     TEXT,
                formtype      TEXT NOT NULL DEFAULT 'PLAIN',
                recvmsgid     TEXT,
                is_rdr        INTEGER NOT NULL DEFAULT 0,
                is_rrr        INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS message_bodies (
                msgidx     INTEGER PRIMARY KEY
                              REFERENCES messages(msgidx)
                              ON UPDATE CASCADE ON DELETE CASCADE,
                message    TEXT
            );
        """)
        # Recreate the view so changes propagate
        conn.execute("DROP VIEW IF EXISTS v_messages_full;")
        conn.execute("""
            CREATE VIEW v_messages_full AS
            SELECT
                m.msgidx,
                m.bbs_call, m.bbsmsgno,
                m.from_call, m.to_call,
                m.subject, m.messagelen,
                m.sent_at, m.rcvd_at,
                m.mstate, m.direction,
                m.is_read, m.is_deleted, m.is_urgent, m.is_encoded, m.is_locked,
                m.is_msgdelreq, m.has_attachment,
                m.header, m.folderidx,
                m.mtype, m.messageid, m.formtype, m.recvmsgid,
                m.is_rdr, m.is_rrr,
                b.message AS body
            FROM messages m
            LEFT JOIN message_bodies b ON b.msgidx = m.msgidx;
        """)
        conn.commit()
