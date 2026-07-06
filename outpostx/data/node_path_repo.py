# data/node_path_repo.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import sqlite3

from .node_path_model import NodeHop, NodePath


class NodePathRepo:
    """
    Persist NodePath (KA-NODE / NET/ROM multi-hop path) for a specific BBS profile.

    Storage strategy (normalized tables):
      - node_paths: one row per BBS profile (bbs_profile_id UNIQUE)
      - node_hops: N rows per path, ordered by hop_order

    This design keeps NODE paths editable and queryable without JSON-in-SQL
    and avoids inflating the existing bbs_profiles table.

    Integration notes:
      - bbs_profiles already stores path_type/path_via for DIGI paths.
      - This repo only persists Path Type = NODE details.
      - NodePath/NodeHop normalization is enforced on read/write.

    Ownership:
      - Schema creation is owned by this repository (self-initializing).
      - Higher-level UI/services decide *when* NODE paths are used.
    """
    def __init__(self, db_path: Path | str) -> None:
        """
        Create a NodePathRepo bound to a SQLite database.

        Args:
            db_path: Path or string path to the SQLite database file.
        """
        self._db = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self) -> None:
        """Create required tables and indexes if they do not exist."""
        with self._connect() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS node_paths (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    bbs_profile_id INTEGER NOT NULL UNIQUE,
                    created_utc    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_utc    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    FOREIGN KEY (bbs_profile_id) REFERENCES bbs_profiles(id) ON DELETE CASCADE
                );
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS node_hops (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_path_id  INTEGER NOT NULL,
                    hop_order     INTEGER NOT NULL,
                    node_name     TEXT NOT NULL,
                    connect_cmd   TEXT NOT NULL,
                    use_next_name INTEGER NOT NULL DEFAULT 1,
                    port_num      INTEGER NOT NULL DEFAULT 0,
                    success_markers TEXT,
                    failure_markers TEXT,
                    FOREIGN KEY (node_path_id) REFERENCES node_paths(id) ON DELETE CASCADE
                );
                """
            )
            c.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_node_hops_path_order "
                "ON node_hops(node_path_id, hop_order);"
            )
            c.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_for_bbs(self, bbs_profile_id: int) -> Optional[NodePath]:
        """
        Load the NODE path for a given BBS profile.

        Returns:
            NodePath if one exists; otherwise None.
        """
        sql = "SELECT id FROM node_paths WHERE bbs_profile_id=?"
        with self._connect() as c:
            row = c.execute(sql, (bbs_profile_id,)).fetchone()
            if not row:
                return None
            node_path_id = int(row["id"])

            hops_rows = c.execute(
                """
                SELECT hop_order, node_name, connect_cmd, use_next_name, port_num,
                       success_markers, failure_markers
                FROM node_hops
                WHERE node_path_id=?
                ORDER BY hop_order ASC
                """,
                (node_path_id,),
            ).fetchall()

        hops: List[NodeHop] = []
        for r in hops_rows:
            hop = NodeHop(
                node_name=r["node_name"] or "",
                connect_cmd=r["connect_cmd"] or "",
                use_next_name=bool(r["use_next_name"]),
                port_num=int(r["port_num"] or 0),
                success_markers=self._decode_markers(r["success_markers"]),
                failure_markers=self._decode_markers(r["failure_markers"]),
            )
            hop.normalize()
            hops.append(hop)

        return NodePath(hops=hops)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_for_bbs(self, bbs_profile_id: int, path: NodePath) -> None:
        """
        Upsert the NODE path for a BBS profile.

        Behavior:
          - Normalizes the NodePath before persistence
          - Creates or updates the node_paths row
          - Replaces all hops atomically (simple + safe)
        """
        path.normalize()

        with self._connect() as c:
            c.execute("BEGIN;")

            row = c.execute(
                "SELECT id FROM node_paths WHERE bbs_profile_id=?",
                (bbs_profile_id,),
            ).fetchone()

            if row:
                node_path_id = int(row["id"])
                c.execute(
                    "UPDATE node_paths SET updated_utc=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                    "WHERE id=?",
                    (node_path_id,),
                )
            else:
                cur = c.execute(
                    "INSERT INTO node_paths(bbs_profile_id) VALUES(?)",
                    (bbs_profile_id,),
                )
                node_path_id = int(cur.lastrowid)

            # Replace hops (simple + safe for now)
            c.execute("DELETE FROM node_hops WHERE node_path_id=?", (node_path_id,))

            for idx, hop in enumerate(path.hops):
                c.execute(
                    """
                    INSERT INTO node_hops(
                        node_path_id, hop_order, node_name, connect_cmd,
                        use_next_name, port_num, success_markers, failure_markers
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        node_path_id,
                        idx,
                        hop.node_name,
                        hop.connect_cmd,
                        1 if hop.use_next_name else 0,
                        int(hop.port_num or 0),
                        self._encode_markers(hop.success_markers),
                        self._encode_markers(hop.failure_markers),
                    ),
                )

            c.commit()

    def delete_for_bbs(self, bbs_profile_id: int) -> None:
        """Delete the NODE path associated with a BBS profile."""
        with self._connect() as c:
            c.execute("DELETE FROM node_paths WHERE bbs_profile_id=?", (bbs_profile_id,))
            c.commit()

    # ------------------------------------------------------------------
    # Marker encoding
    # ------------------------------------------------------------------
    @staticmethod
    def _encode_markers(markers: List[str]) -> str:
        """Encode marker strings for storage (newline-separated)."""
        # newline-separated; easy for humans + UIs
        return "\n".join([m.strip() for m in (markers or []) if (m or "").strip()])

    @staticmethod
    def _decode_markers(text: str | None) -> List[str]:
        """Decode stored marker text into a list of strings."""
        if not text:
            return []
        out: List[str] = []
        for line in text.splitlines():
            t = line.strip()
            if t:
                out.append(t)
        return out
