# services/sqlite_message_service.py

from __future__ import annotations
from typing import Optional, Tuple, List

# NOTE: Contract freeze — MessagePayload is imported from services.message_service
# as the single source of truth for the editor/service boundary.
from services.message_service import MessagePayload
from services.message_service import MessageService
from data.message_model import MessageType, FormType
from data.message_repo import MessageRepository

import re
import sqlite3

class SqliteMessageService(MessageService):
    """
    Adapter between the UI MessagePayload and the SQLite-backed MessageRepository.

    This is the MessageFormWindow-facing "message lifecycle" service. It implements
    the semantics expected by the QMainWindow-based Message Form:

    - save_draft(): create/update an outbound draft
    - queue_send(): validate + queue for send + move to Outbox
    - delete_to_trash(): soft-delete (move to Trash)
    - make_reply()/make_forward(): create new drafts from an existing message
    - make_resend(): create a resend draft from an existing message, preserving
        or replacing the local MID depending on operator choice

    Folder placement rules:
    - New drafts go to the root "Drafts" folder if it exists, else the default outbound.
    - Queued messages move to root "Outbox" if it exists, else remain in default outbound.
    - Reply/Forward/Resend drafts are created as editable outbound drafts.

    Contract:
    - msg_repo must provide create_outbound(), update_outbound_from_editor(),
        queue_for_send(), move_to_folder(), move_to_trash(), and get().
    - profiles_repo must provide list_bbs_calls() and may optionally provide
        get_active_bbs_name().
    - app_settings must provide get_default_from_call().
    - MessageFormWindow owns menus, toolbar, status bar, and user actions;
        this service owns message lifecycle and persistence semantics.

    Legacy note:
    ComposeMessageDialog and ViewMessageDialog have been retired/quarantined.
    Do not add new message-form behavior to those legacy hosts.
    """

    def __init__(self, msg_repo: MessageRepository, profiles_repo, app_settings):
        """
        Create the service.

        Args:
            msg_repo: Repository for reading/writing messages and folders.
            profiles_repo: Adapter used to supply BBS names to the editor defaults.
            app_settings: Adapter used to supply default From callsign.
        """
        self.msg_repo = msg_repo
        self.profiles_repo = profiles_repo
        self.app_settings = app_settings

        # Cache root folder ids if they exist
        self._drafts_folderidx: Optional[int] = self._find_root_folder("Drafts")
        self._outbox_folderidx: Optional[int] = self._find_root_folder("Outbox")

    # ------------------------------------------------------------------
    # UI defaults
    # ------------------------------------------------------------------
    def defaults(self) -> Tuple[List[str], str]:
        """
        Returns (bbs_calls, default_from_call) for the editor's BBS & From combo.

        BBS behavior (IRS 5.1.2):

        - If an *active* BBS is configured:
            - Ensure it appears first in the list so the combo shows it by default.
        - If there is at least one BBS configured but *none* are active:
            - Insert a blank entry at the front so the field starts blank.
        - If there are no BBS profiles at all:
            - Fall back to ["(Unassigned)"] as before.

        FROM behavior (IRS 5.1.2/5.1.3):

        - Delegated to EditorAppSettings.get_default_from_call(), which applies:
            - No active Station → blank
            - Station active only → Station legal call
            - Station + Tactical active → Tactical call
        """
        # All configured BBS names
        bbs_calls = self.profiles_repo.list_bbs_calls() or []
        default_from = (self.app_settings.get_default_from_call() or "").strip()

        if not bbs_calls:
            # No BBS profiles defined at all → keep the simple placeholder
            return ["(Unassigned)"], default_from

        # Try to reorder so the active BBS is first if the adapter supports it
        get_active = getattr(self.profiles_repo, "get_active_bbs_call", None)
        if callable(get_active):
            active_name = (get_active() or "").strip()
            if active_name and active_name in bbs_calls:
                # Move active to front, keep the rest in order
                bbs_calls = [active_name] + [n for n in bbs_calls if n != active_name]
            else:
                # No active BBS → insert a blank entry at the front so the field starts blank
                bbs_calls = [""] + bbs_calls

        return bbs_calls, default_from

    # ------------------------------------------------------------------
    # Draft handling
    # ------------------------------------------------------------------
        # Identity note:
        # - The editor payload contains bbs_name as a user-facing string.
        # - Persistence should store BOTH:
        #     (a) stable identifiers (bbs_profile_id / station_profile_id) when available
        #     (b) callsign strings (bbs_call/from_call) for display and legacy compatibility
        # - Send/Receive eligibility should prefer IDs, using strings only as a safety backstop.

    def save_draft(self, payload: MessagePayload, message_id: Optional[int]) -> int:
        """
        Create or update an OUTBOUND draft.

        - If message_id is None: create a NEW outbound row in the
          'Drafts' root folder (if present), else in the default outbound folder.
        - If message_id is set: update all editable fields of the existing message
          (From/To/Subject/BBS/type/flags/body).
        """
        norm = self._normalized(payload)
        mtype = self._map_ui_type_to_message_type(norm.type)
        formtype = FormType.PLAIN  # editor is plain text for now

        if message_id:
            msgidx = int(message_id)
            self.msg_repo.update_outbound_from_editor(
                msgidx=msgidx,
                from_call=norm.from_call,
                to_call=norm.to_call,
                subject=norm.subject,
                body_text=norm.body,
                bbs_call=norm.bbs_name,
                mtype=mtype,
                formtype=formtype,
                request_delivery_receipt=norm.req_delivery_rcpt,
                request_read_receipt=norm.req_read_rcpt,
                urgent=norm.urgent,
                encoded=norm.base64_encode,
                messageid=None,
            )
            # ------------------------------------------------------------
            # #67/260808:
            # SAVE always returns an unsent message to DRAFT state.
            # If it had previously been QUEUED, remove it from the send queue
            # and move it back to the Drafts folder.
            # ------------------------------------------------------------
            self.msg_repo.mark_draft(msgidx)

            drafts_idx = self._drafts_folderidx or self._default_outbound_folderidx()
            if drafts_idx is not None:
                self.msg_repo.move_to_folder(msgidx, drafts_idx)

            return msgidx

        # New draft → create_outbound as DRAFT OUTBOUND in Drafts, if available
        folderidx = self._drafts_folderidx or self._default_outbound_folderidx()

        msgidx = self.msg_repo.create_outbound(
            from_call=norm.from_call,
            to_call=norm.to_call,
            subject=norm.subject,
            body_text=norm.body,
            bbs_call=norm.bbs_name,
            folderidx=folderidx,
            mtype=mtype,
            formtype=formtype,
            request_delivery_receipt=norm.req_delivery_rcpt,
            request_read_receipt=norm.req_read_rcpt,
            urgent=norm.urgent,
            encoded=norm.base64_encode,
            messageid=None,
        )
        return int(msgidx)

    # ------------------------------------------------------------------
    # Queue / send
    # ------------------------------------------------------------------
    def queue_send(self, payload: MessagePayload, message_id: Optional[int]) -> int:
        """
        Ensure the message content is saved, then mark it QUEUED for sending
        and move it to the Outbox.

        - If message_id is None: creates the row (in Drafts), then queues it
          and moves it to Outbox.
        - If message_id exists: updates all fields, then queues it and
          moves it to Outbox.
        """
        norm = self._normalized(payload)
        self._validate_for_send(norm)

        # Save content first (create or update)
        msgidx = self.save_draft(norm, message_id)

        # Change state to QUEUED
        self.msg_repo.queue_for_send(msgidx)

        # Move to Outbox root if available, else keep in default outbound folder
        outbox_idx = self._outbox_folderidx or self._default_outbound_folderidx()
        if outbox_idx is not None:
            self.msg_repo.move_to_folder(msgidx, outbox_idx)

        return msgidx

    # ------------------------------------------------------------------
    # Delete / Trash
    # ------------------------------------------------------------------
    def delete_to_trash(self, message_id: int) -> None:
        """
        Soft-delete a message by moving it to Trash.

        This is non-destructive: the row remains in SQLite and can be restored
        later (future feature) or purged by a maintenance operation.
        """
        self.msg_repo.move_to_trash(int(message_id))

    # ------------------------------------------------------------------
    # Reply / Forward / Resend creation
    # 260517 - Add Resend
    # ------------------------------------------------------------------
    def make_reply(self, orig_message_id: int, reply_all: bool = False) -> int:
        """
        Create a reply draft based on an existing message, returning the new msgidx.

        For now:
        - Uses the original message's BBS.
        - Reply messages always default to PRIVATE. #41
        - Sets From = default from-call from app settings.
        - Sets To   = original FROM.
        - Subject is prefixed with 'RE:' unless it already starts with RE:.
        - Body is prefilled with:

            On <sent_at or rcvd_at>, <from_call> wrote:
            > original line 1
            > original line 2
            ...

        - Ignores reply_all (no CC list yet).
        """
        got = self.msg_repo.get(int(orig_message_id))
        if not got:
            # No original → fabricate an empty reply
            payload = MessagePayload(
                bbs_name="",
                from_call=self._default_from(),
                to_call="",
                subject="RE:",
                body="",
                type="private",
                urgent=False,
                req_delivery_rcpt=False,
                req_read_rcpt=False,
                base64_encode=False,
            )
            return self.save_draft(payload, None)

        msg, body = got
        subject = self._prefix_subject("RE:", msg.subject or "")
        original_body = (body.message if body else "") or ""
        quoted_body = self._build_quoted_body(msg, original_body)

        payload = MessagePayload(
            bbs_name=(msg.bbs_call or ""),
            from_call=self._default_from(),
            to_call=(msg.from_call or ""),
            subject=subject,
            body="\n\n" + quoted_body,
            type="private",
            # type=self._ui_type_from_message_type(msg.mtype),  # #41, change reply to PRIVATE
            urgent=False,
            req_delivery_rcpt=False,
            req_read_rcpt=False,
            base64_encode=False,
        )
        return self.save_draft(payload, None)

    def make_forward(self, orig_message_id: int) -> int:
        """
        Create a forward draft based on an existing message, returning the new msgidx.

        - Uses the original message's BBS.
        - Forward messages always default to PRIVATE. #41
        - Sets From = default from-call.
        - Leaves To   empty (user chooses the destination).
        - Subject is prefixed with 'FW:' unless it already starts with FW:.
        - Body uses the same quoted structure as replies:

            On <sent_at or rcvd_at>, <from_call> wrote:
            > original line 1
            > original line 2
        """
        got = self.msg_repo.get(int(orig_message_id))
        if not got:
            # No original → fabricate an empty forward
            payload = MessagePayload(
                bbs_name="",
                from_call=self._default_from(),
                to_call="",
                subject="FW:",
                body="",
                type="private",
                urgent=False,
                req_delivery_rcpt=False,
                req_read_rcpt=False,
                base64_encode=False,
            )
            return self.save_draft(payload, None)

        msg, body = got
        subject = self._prefix_subject("FW:", msg.subject or "")
        original_body = (body.message if body else "") or ""
        quoted_body = self._build_quoted_body(msg, original_body)

        payload = MessagePayload(
            bbs_name=(msg.bbs_call or ""),
            from_call=self._default_from(),
            to_call="",  # user will pick destination
            subject=subject,
            body="\n\n" + quoted_body,
            type="private",
            # type=self._ui_type_from_message_type(msg.mtype),  # 41, change forward to PRIVATE
            urgent=False,
            req_delivery_rcpt=False,
            req_read_rcpt=False,
            base64_encode=False,
        )
        return self.save_draft(payload, None)


    def make_resend(self, orig_message_id: int, *, new_message_id: str = "") -> int:
        """
        Create a resend draft from an existing message.
        - Uses the original message's BBS and message Type.

        If new_message_id is blank:
        - preserve the existing subject and local messageid.

        If new_message_id is provided:
        - replace a leading MID only when followed by space or underscore.
        - otherwise prepend the new MID.
        """
        got = self.msg_repo.get(int(orig_message_id))
        if not got:
            payload = MessagePayload(
                bbs_name="",
                from_call=self._default_from(),
                to_call="",
                subject=new_message_id or "",
                body="",
                type="private",
                urgent=False,
                req_delivery_rcpt=False,
                req_read_rcpt=False,
                base64_encode=False,
            )
            return self.save_draft(payload, None)

        msg, body = got
        original_subject = msg.subject or ""
        original_body = (body.message if body else "") or ""

        subject = original_subject
        if new_message_id:
            subject = self._replace_or_prepend_subject_mid(
                original_subject,
                new_message_id,
            )

        payload = MessagePayload(
            bbs_name=(msg.bbs_call or ""),
            from_call=self._default_from(),
            to_call=(msg.to_call or ""),
            subject=subject,
            body=original_body,
            type=self._ui_type_from_message_type(msg.mtype),
            urgent=bool(getattr(msg, "is_urgent", False)),
            req_delivery_rcpt=bool(getattr(msg, "is_rdr", False)),
            req_read_rcpt=False,
            base64_encode=bool(getattr(msg, "is_encoded", False)),
        )

        new_idx = self.save_draft(payload, None)

        # Same-MID resend: preserve old local messageid when possible.
        # New-MID resend: store caller-supplied new MID.
        mid_to_store = new_message_id or (getattr(msg, "messageid", "") or "")
        if mid_to_store:
            try:
                self.msg_repo.update_outbound_from_editor(
                    msgidx=new_idx,
                    from_call=payload.from_call,
                    to_call=payload.to_call,
                    subject=payload.subject,
                    body_text=payload.body,
                    bbs_call=payload.bbs_name,
                    mtype=self._map_ui_type_to_message_type(payload.type),
                    formtype=FormType.PLAIN,
                    request_delivery_receipt=payload.req_delivery_rcpt,
                    request_read_receipt=payload.req_read_rcpt,
                    urgent=payload.urgent,
                    encoded=payload.base64_encode,
                    messageid=mid_to_store,
                )
            except Exception:
                pass

        return int(new_idx)


    def _replace_or_prepend_subject_mid(self, subject: str, new_mid: str) -> str:
        """
        Replace a leading MID only when followed by space or underscore.

        Supported:
        CUP123 Subject
        CUP123P Subject
        CUP-123 Subject
        CUP-123P_Subject
        CUP-123P_R_Subject

        Unsupported/no delimiter:
        CUP-123Subject

        In unsupported cases, prepend the new MID and leave original text intact.
        """
        subject = subject or ""
        new_mid = (new_mid or "").strip().upper()
        if not new_mid:
            return subject

        # MID at start, followed by required delimiter: space or underscore.
        pat = re.compile(
            r"^(?P<mid>[A-Z0-9]+-?\d+[A-Z]?)(?P<sep>[ _])(?P<rest>.*)$",
            re.IGNORECASE,
        )
        m = pat.match(subject.strip())

        if m:
            return f"{new_mid}{m.group('sep')}{m.group('rest')}"

        return f"{new_mid} {subject}".strip()



    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _default_from(self) -> str:
        """Return the editor default From callsign (station/tactical selection)."""
        return (self.app_settings.get_default_from_call() or "").strip()

    def _normalized(self, p: MessagePayload) -> MessagePayload:
        """
        Return a normalized copy of the payload: stripped strings and sane defaults.
        """
        t = (p.type or "private").strip().lower()
        if t not in ("private", "bulletin", "nts"):
            t = "private"

        return MessagePayload(
            bbs_name=(p.bbs_name or "").strip(),
            from_call=(p.from_call or "").strip(),
            to_call=(p.to_call or "").strip(),
            subject=(p.subject or "").strip(),
            body=p.body or "",
            type=t,
            urgent=bool(p.urgent),
            req_delivery_rcpt=bool(p.req_delivery_rcpt),
            req_read_rcpt=bool(p.req_read_rcpt),
            base64_encode=bool(p.base64_encode),
        )

    def _validate_for_send(self, p: MessagePayload) -> None:
        """
        Basic sanity checks for Send/Queue.
        """
        if not p.bbs_name:
            raise ValueError("BBS is required to send.")
        if p.type != "bulletin" and not p.to_call:
            raise ValueError("TO is required to send non-bulletin messages.")
        if not p.subject:
            raise ValueError("Subject is required to send.")
        if not (p.body or "").strip():
            raise ValueError("Body is required to send.")

    def _map_ui_type_to_message_type(self, ui_type: str) -> MessageType:
        """Map UI type string ("private"/"bulletin"/"nts") to MessageType enum."""
        t = (ui_type or "private").strip().lower()
        if t == "bulletin":
            return MessageType.BULLETIN
        if t == "nts":
            return MessageType.NTS
        return MessageType.PRIVATE

    def _ui_type_from_message_type(self, mtype: MessageType) -> str:
        """Map MessageType enum back to UI type string."""
        if mtype == MessageType.BULLETIN:
            return "bulletin"
        if mtype == MessageType.NTS:
            return "nts"
        return "private"

    # 251128 REPLACED w/ try/except so a missing table just returns None instead of blowing up
    def _find_root_folder(self, name: str) -> Optional[int]:
        """
        Look up a root folder ID by name.

        Returns None if the folders table is missing (early startup) or the
        named root folder does not exist.
        """
        dao = getattr(self.msg_repo, "dao", None)
        if dao is None or not hasattr(dao, "_connect"):
            return None

        try:
            with dao._connect() as conn:
                row = conn.execute(
                    "SELECT folderidx FROM folders WHERE name=? AND parentidx IS NULL",
                    (name,),
                ).fetchone()
        except sqlite3.OperationalError:
            # e.g., folders table not created yet
            return None

        if not row:
            return None
        return int(row["folderidx"])


    def _default_outbound_folderidx(self) -> Optional[int]:
        """
        Return the configured default outbound folder index.

        Used as a fallback when the standard root folders (Drafts/Outbox)
        are missing.
        """
        cfg = getattr(self.msg_repo, "cfg", None)
        if cfg is None:
            return None
        return getattr(cfg, "default_outbound_folderidx", None)

    # ----- subject / body helpers for reply/forward -------------------
    def _prefix_subject(self, prefix: str, subject: str) -> str:
        """
        Ensure subject starts with the given prefix (e.g. 'RE:' or 'FW:'),
        without double-prefixing if it already does.
        """
        subject = subject or ""
        stripped = subject.lstrip()
        upper = stripped.upper()
        if upper.startswith(prefix.upper()):
            return subject
        return f"{prefix} {subject}".strip()

    def _build_quoted_body(self, msg, original_body: str) -> str:
        """
        Build the body text for a reply/forward, including the
        'On <sent_at>, <from_call> wrote:' header and quoted original.
        """
        when = getattr(msg, "sent_at", None) or getattr(msg, "rcvd_at", None) or ""
        from_call = getattr(msg, "from_call", "") or ""

        header_line = f"On {when}, {from_call} wrote:".strip()

        original_body = original_body or ""
        lines = original_body.splitlines()
        if lines:
            quoted = "\n".join(f"> {line}" for line in lines)
        else:
            quoted = ">"

        if header_line and quoted:
            return f"{header_line}\n{quoted}"
        elif header_line:
            return header_line
        else:
            return quoted
