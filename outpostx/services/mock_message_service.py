# FILE: services/mock_message_service.py
"""In-memory MessageService for development & UI testing.

Use this when BBS/UserID config and repositories are not ready yet. It
returns a safe default BBS list and stores drafts/queued messages in RAM.
"""
from __future__ import annotations
from typing import Optional, Tuple, List, Dict
import itertools

from widgets.message_editor import MessagePayload
from services.message_service import MessageService


class MockMessageService(MessageService):
    """A simple, non-persistent message service for UI bring-up.

    - Provides defaults() without requiring BBS/UserID config
    - Stores drafts/queued items in memory
    - Fabricates reply drafts by quoting the original body
    """
    _ids = itertools.count(1000)  # deterministic ids for testing

    def __init__(self,
                 default_bbses: Optional[List[str]] = None,
                 default_from: str = "KN6PE") -> None:
        self._bbses = default_bbses or ["(Unassigned)", "W6XSC-1", "N6NFI-1"]
        self._default_from = default_from
        self._items: Dict[int, MessagePayload] = {}
        self._status: Dict[int, str] = {}  # "draft" | "queued"

    # --- adapter API ---
    def defaults(self) -> Tuple[List[str], str]:
        return list(self._bbses), self._default_from

    def save_draft(self, payload: MessagePayload, message_id: Optional[int]) -> int:
        if not message_id:
            message_id = next(self._ids)
        self._items[message_id] = payload
        self._status[message_id] = "draft"
        return message_id

    def queue_send(self, payload: MessagePayload, message_id: Optional[int]) -> int:
        mid = self.save_draft(payload, message_id)
        self._status[mid] = "queued"
        return mid

    def delete_to_trash(self, message_id: int) -> None:
        self._items.pop(message_id, None)
        self._status.pop(message_id, None)

def make_reply(self, orig_message_id: int, reply_all: bool = False) -> int:
    """Create a reply draft in-memory and return its new id.

    - If the original isn't found, fabricate a minimal quoted body.
    - `reply_all` is currently ignored in the mock (no CC list),
      but the signature matches the real service so callers don't care.
    """
    orig = self._items.get(orig_message_id)
    if not orig:
        orig = MessagePayload(subject="", body="(original message not available)")

    # Build a quoted body safely (works even if empty)
    original_lines = (orig.body or "").splitlines()
    quoted = "> " + "\n> ".join(original_lines) if original_lines else ">"

    new_payload = MessagePayload(
        bbs_name=orig.bbs_name or (self._bbses[0] if self._bbses else "(Unassigned)"),
        from_call=self._default_from,
        to_call=orig.from_call,  # simple reply-to; ignore reply_all in mock
        subject=(f"RE: {orig.subject}" if orig.subject else "RE:"),
        body=("\n\nOn previous message wrote:\n" + quoted),
        type=orig.type,
        urgent=False,
        req_delivery_rcpt=False,
        req_read_rcpt=False,
        base64_encode=False,
    )
    return self.save_draft(new_payload, None)

    # --- convenience for demos/tests ---
    def get(self, message_id: int) -> Optional[MessagePayload]:
        return self._items.get(message_id)

    def list_ids(self) -> List[int]:
        return list(self._items.keys())
