-- ============================================================================
-- OutpostX Message Schema
-- ============================================================================
--
-- This SQL file defines the canonical SQLite schema for message storage in
-- OutpostX. It is the authoritative database contract for:
--
--   * messages           (message headers + lifecycle state)
--   * message_bodies     (message text payloads)
--   * v_messages_full    (header + body convenience view)
--
-- Architectural context
-- ---------------------
-- * message_model.py mirrors these tables exactly at the dataclass level.
-- * MessageDAO is responsible for executing INSERT/UPDATE/SELECT operations.
-- * MessageRepository owns lifecycle semantics (state, folders, flags).
-- * schema_bootstrap.py ensures this schema exists on first run.
--
-- Design principles
-- -----------------
-- * Headers and bodies are separated for performance and partial reads.
-- * Boolean fields are stored as INTEGER (0/1).
-- * Message length (messagelen) is computed by triggers to avoid duplication.
-- * The v_messages_full view is DROP/CREATE safe and may be regenerated at startup.
--
-- IMPORTANT
-- ---------
-- This file is not a migration system.
-- Any schema changes here must be reflected in:
--   - message_model.py
--   - MessageDAO mappings
--   - v_messages_full column ordering
-- ============================================================================

-- message_schema.sql
-- OutpostX Message schema (SQLite)
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------
-- Table: folders
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS folders (
    folderidx   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    parentidx   INTEGER REFERENCES folders(folderidx)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE(name, parentidx)
);

-- Seed default folders (only if empty)
INSERT INTO folders (name, parentidx)
SELECT 'Inbox', NULL
WHERE NOT EXISTS (SELECT 1 FROM folders WHERE name='Inbox');

INSERT INTO folders (name, parentidx)
SELECT 'Outbox', NULL
WHERE NOT EXISTS (SELECT 1 FROM folders WHERE name='Outbox');

INSERT INTO folders (name, parentidx)
SELECT 'Trash', NULL
WHERE NOT EXISTS (SELECT 1 FROM folders WHERE name='Trash');


-- =========================
-- Header table: messages
-- =========================
CREATE TABLE IF NOT EXISTS messages (
  -- Identity
  msgidx        INTEGER PRIMARY KEY,                         -- internal pointer/ID
  bbs_call      TEXT    NOT NULL CHECK(length(bbs_call) <= 10),
  bbsmsgno      TEXT    CHECK(length(bbsmsgno) <= 16),       -- LM-listed number (rcvd) or NULL (send)

  -- Addressing
  from_call     TEXT    NOT NULL CHECK(length(from_call) <= 256),
  to_call       TEXT    NOT NULL CHECK(length(to_call)   <= 1024),

  -- Content meta
  subject       TEXT    NOT NULL DEFAULT '' CHECK(length(subject) <= 256),
  messagelen    INTEGER NOT NULL DEFAULT 0 CHECK(messagelen >= 0),

  -- Timestamps (store as UTC ISO-8601 text, e.g., '2025-11-07T23:15:00Z')
  sent_at       TEXT,     -- time message was sent from this station to BBS (sender-set, UTC)
  rcvd_at       TEXT,     -- time message was actually downloaded from BBS (UTC)

  -- State & direction
  mstate        TEXT    NOT NULL CHECK(mstate IN ('NEW','DRAFT','QUEUED','SENT','POST_REMOTE','RECEIVED')),
  direction     TEXT    NOT NULL CHECK(direction IN ('INBOUND','OUTBOUND')),

  -- Flags (0/1)
  is_read       INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),
  is_deleted    INTEGER NOT NULL DEFAULT 0 CHECK(is_deleted IN (0,1)),
  is_urgent     INTEGER NOT NULL DEFAULT 0 CHECK(is_urgent IN (0,1)),
  is_encoded    INTEGER NOT NULL DEFAULT 0 CHECK(is_encoded IN (0,1)),
  is_locked     INTEGER NOT NULL DEFAULT 0 CHECK(is_locked IN (0,1)),
  is_msgdelreq  INTEGER NOT NULL DEFAULT 0 CHECK(is_msgdelreq IN (0,1)),
  has_attachment INTEGER NOT NULL DEFAULT 0 CHECK(has_attachment IN (0,1)),  -- FUTURE

  -- Parsed header (received only)
  header        TEXT,

  -- Folder and typing
  folderidx     INTEGER NOT NULL, -- FK to folders(folderidx) if you maintain a folders table
  mtype         INTEGER NOT NULL CHECK(mtype IN (0,1,2)),   -- 0=Private,1=NTS,2=Bulletin (app mapping)

  -- IDs and forms
  messageid     TEXT CHECK(length(messageid) <= 16),         -- subject prefix (e.g., CUP-102P)
  formtype      TEXT NOT NULL CHECK(formtype IN ('PLAIN','PACFORM','ICS213','MARS','NTSF','ADDON')),
  recvmsgid     TEXT CHECK(length(recvmsgid) <= 16),         -- assigned by receiving station

  -- Receipts
  is_rdr        INTEGER NOT NULL DEFAULT 0 CHECK(is_rdr IN (0,1)), -- Request Delivery Receipt (!RDR!)
  is_rrr        INTEGER NOT NULL DEFAULT 0 CHECK(is_rrr IN (0,1)) -- Request Read Receipt (!RRR!)

  -- Optional FK (uncomment if folders table exists)
  -- NOTE:  put ',' back in after is_rrr if uncommenting these lines
  -- FOREIGN KEY(folderidx) REFERENCES folders(folderidx) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- =========================
-- Body table: message_bodies
-- =========================
CREATE TABLE IF NOT EXISTS message_bodies (
  msgidx   INTEGER PRIMARY KEY, -- 1:1 with messages.msgidx
  message  TEXT    NOT NULL,    -- actual message text (any size)
  FOREIGN KEY(msgidx) REFERENCES messages(msgidx) ON DELETE CASCADE
);

-- =========================
-- Triggers to maintain messagelen
-- =========================
CREATE TRIGGER IF NOT EXISTS trg_message_body_after_insert
AFTER INSERT ON message_bodies
BEGIN
  UPDATE messages SET messagelen = length(NEW.message) WHERE msgidx = NEW.msgidx;
END;

CREATE TRIGGER IF NOT EXISTS trg_message_body_after_update
AFTER UPDATE OF message ON message_bodies
BEGIN
  UPDATE messages SET messagelen = length(NEW.message) WHERE msgidx = NEW.msgidx;
END;

CREATE TRIGGER IF NOT EXISTS trg_message_body_after_delete
AFTER DELETE ON message_bodies
BEGIN
  UPDATE messages SET messagelen = 0 WHERE msgidx = OLD.msgidx;
END;

-- =========================
-- Useful indexes
-- =========================
-- Fast folder views & unread filters
CREATE INDEX IF NOT EXISTS idx_messages_folder ON messages(folderidx);
CREATE INDEX IF NOT EXISTS idx_messages_folder_read ON messages(folderidx, is_read);

-- State & direction filters
CREATE INDEX IF NOT EXISTS idx_messages_state ON messages(mstate);
CREATE INDEX IF NOT EXISTS idx_messages_direction ON messages(direction);

-- BBS correlation (inbound uniqueness & list syncs)
CREATE INDEX IF NOT EXISTS idx_messages_bbs ON messages(bbs_call, bbsmsgno);

-- Time-based queries
CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);
CREATE INDEX IF NOT EXISTS idx_messages_rcvd_at ON messages(rcvd_at);

-- Receipts and deletes
CREATE INDEX IF NOT EXISTS idx_messages_receipts ON messages(is_rdr, is_rrr);
CREATE INDEX IF NOT EXISTS idx_messages_deleted ON messages(is_deleted);

-- Partial uniqueness (SQLite supports partial UNIQUE via indexes)
-- Ensure we don't import the same inbound BBS message twice when bbsmsgno is known:
CREATE UNIQUE INDEX IF NOT EXISTS uq_inbound_bbsmsg
ON messages(bbs_call, bbsmsgno)
WHERE direction = 'INBOUND' AND bbsmsgno IS NOT NULL;

-- =========================
-- Convenience view (joined)
-- =========================
CREATE VIEW IF NOT EXISTS v_messages_full AS
SELECT
  m.*,
  b.message AS body
FROM messages m
LEFT JOIN message_bodies b ON b.msgidx = m.msgidx;
