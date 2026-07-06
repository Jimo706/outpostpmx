# FILE: services/message_service.py
"""
Message service interface (UI-facing contract).

This module defines the abstract service API used by the UI layer to work with
messages without depending on a specific persistence backend.

Architectural role:
- UI widgets/dialogs talk to MessageService, not to DAOs or repositories.
- Concrete implementations (e.g., SqliteMessageService) provide behavior by
  delegating to repositories/DAOs and enforcing lifecycle rules.
- The service exposes UI-native data shapes (MessagePayload, TransportMeta)
  rather than database row models.

Why this boundary matters:
- The UI remains stable even as storage schema or workflow rules evolve.
- Unit tests can substitute a fake/in-memory implementation for UI testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass
class MessagePayload:
    """UI-native representation of a message.

    This is the shape dialogs/widgets use for compose/edit/view.
    Implementations translate this payload to and from the database
    message model (Message + MessageBody).
    """
    bbs_name: str
    from_call: str
    to_call: str
    subject: str
    body: str
    type: str  # "private", "bulletin", "nts"
    urgent: bool
    req_delivery_rcpt: bool
    req_read_rcpt: bool
    base64_encode: bool = False


@dataclass
class TransportMeta:
    """Non-editable metadata that accompanies a message payload.

    Originally this carried only transport/session information.  It now also
    carries read-only display metadata used by the Message Form OPEN view.

    These fields are not editable message content and should not be included
    in MessagePayload.
    """
    interface_name: str = ""

    # Message display/lifecycle metadata
    message_state: str = ""     # e.g. NEW, DRAFT, QUEUED, SENT, RECEIVED
    sent_at: str = ""           # when message was sent, if known
    rcvd_at: str = ""           # when message was received locally, if known
    local_msg_id: str = ""      # local MID, typically recvmsgid or messageid


class MessageService:
    """
    Message Form / Editor Contract (freeze boundary)

    MessageFormWindow is the active QMainWindow host for MessageEditorWidget.
    MessageEditorWidget remains the reusable content widget. Together, they
    communicate with the application layer strictly via:

    - MessagePayload: the editable user-facing message fields
    - TransportMeta (optional): non-editable transport/session/display metadata
    - message_id (Optional[int]): database identity for an existing message row

    Rules:
    1) The editor never writes to the DB directly.
    2) MessageFormWindow is wiring/control only:
        - owns menus, toolbar, status bar, and context menu actions
        - forwards Save/Send/Delete/Reply/Forward/Resend actions to MessageService
        - updates editor/window state with returned message_id
        - does not “fix up” or transform payload fields
    3) MessageService owns lifecycle semantics:
        - save_draft() creates/updates and returns the authoritative message_id
        - queue_send() validates/queues/moves folders and returns the authoritative message_id
        - delete_to_trash() is a soft-delete
        - make_reply()/make_forward()/make_resend() create new draft messages
    4) Defaults are provided by defaults() and must remain stable:
        defaults() -> (bbs_calls: List[str], default_from_call: str)

    Legacy note:
    ComposeMessageDialog and ViewMessageDialog have been retired/quarantined
    and should not be used for new message-form work.

    If this contract must change, update:
    - MessageService doc + interface
    - MessageEditorWidget collect_payload()/set_message()
    - MessageFormWindow wiring
    together in the same commit.
    """
    # ------------------------------------------------------------------
    # UI defaults
    # ------------------------------------------------------------------
    def defaults(self) -> Tuple[List[str], str]:
        """Return (bbs_calls, default_from_call)."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Draft / outbound lifecycle
    # ------------------------------------------------------------------
    def save_draft(self, payload: MessagePayload, message_id: Optional[int]) -> int:
        """Insert or update a draft message; returns message_id."""
        raise NotImplementedError

    def queue_send(self, payload: MessagePayload, message_id: Optional[int]) -> int:
        """Insert/update and mark the message as queued for send."""
        raise NotImplementedError

    def delete_to_trash(self, message_id: int) -> None:
        """Move a message to the 'Trash' folder (soft delete)."""
        raise NotImplementedError

    def load_payload(self, message_id: int) -> Tuple[MessagePayload, Optional[TransportMeta]]:
        """Load a message for editing (draft) or viewing."""
        raise NotImplementedError

    def make_reply(self, message_id: int) -> MessagePayload:
        """Construct a reply payload from an existing message."""
        raise NotImplementedError

    def make_forward(self, message_id: int) -> MessagePayload:
        """Construct a forward payload from an existing message."""
        raise NotImplementedError
