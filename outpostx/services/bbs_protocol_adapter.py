# services/bbs_protocol_adapter.py
"""
BBS protocol adapter (spec-driven parsing + conservative fallbacks).

This module provides:
- SID parsing (parse_sid) to detect the remote BBS/TNC "flavor"
- ParsedInboundMessage: a loose, minimal normalized shape for inbound storage
- BBSProtocolAdapter: a wrapper around a BBS profile that exposes a small set of
  protocol behaviors used by SendReceiveSession (list/read/send command strings
  and parsers).

The adapter supports two modes:

1) Generic mode (no spec bound)
   - Uses safe heuristics to extract message numbers and common header fields.
   - Intended to "do no harm" while you iterate on spec coverage.

2) Spec mode (bind_spec / bind_spec_for_sid_type)
   - Uses a BBSSpec (loaded via BBSSpecLoader) to drive prompt patterns and
     message listing / read parsing.

Important boundaries:
- This adapter does not perform transport I/O. That is owned by SendReceiveAdapter / BaseConnection.
- This adapter does not write to the database. That is owned by MessageRepository / SqliteMessageService.
- This adapter does not own UI concerns. That is owned by SendReceiveSessionDialog / MainWindow.

As you add more BBS types, the spec files become the authoritative source of
parsing patterns, leaving this module mostly stable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Sequence, Dict

from services.bbs_spec_loader import BBSSpec, BBSSpecLoader


# ----------------------------------------------------------------------
# SID parsing
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ParsedSID:
    """Parsed bracketed SID token (raw + type)."""
    sid_raw: str
    sid_type: str


def parse_sid(text: str) -> Optional[ParsedSID]:
    """
    Find a bracketed SID like:
      [WL2K-5.0-B2FWIHJM$]
      [KPC3P-8.3-HM$]
      [JNOS-2.0k.2.xsc.8-B1FHIM$]
      [BPQ-6.0.24.1-B2FWIHJM$]

    Returns ParsedSID(sid_raw='[KPC3P-8.3-HM$]', sid_type='KPC3P')
    where sid_type is token before the first '-'.
    """
    if not text:
        return None

    m = re.search(r"\[([A-Za-z0-9]+)-([^\]]+)\]", text)
    if not m:
        return None

    sid_type = (m.group(1) or "").strip().upper()
    sid_raw = m.group(0)
    if not sid_type:
        return None
    return ParsedSID(sid_raw=sid_raw, sid_type=sid_type)


# ----------------------------------------------------------------------
# Parsed message dataclass (keep your existing shape)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ParsedInboundMessage:
    """
    Minimal normalized inbound message shape.

    This is the *parser output* shape used by protocol adapters. It stays
    deliberately loose because different BBS types expose different header
    fields, and OutpostX will evolve its inbound storage pipeline.

    Notes:
      - bbs_call and bbsmsgno identify the message on the remote BBS.
      - header is optional raw header text (useful for diagnostics).
      - sent_at is ISO (naive/local) when available.
    """
    bbs_call: str
    bbsmsgno: str
    from_call: str = ""
    to_call: str = ""
    subject: str = ""
    header: Optional[str] = None
    body: str = ""
    sent_at: Optional[str] = None  # ISO if you have it; else None
    recvmsgid: Optional[str] = None
    urgent: bool = False
    encoded: bool = False
    request_delivery_receipt: bool = False
    request_read_receipt: bool = False

    def to_dict(self) -> dict:
        return {
            "bbs_call": self.bbs_call,
            "bbsmsgno": self.bbsmsgno,
            "from_call": self.from_call,
            "to_call": self.to_call,
            "subject": self.subject,
            "header": self.header,
            "body": self.body,
            "sent_at": self.sent_at,
            "recvmsgid": self.recvmsgid,
            "urgent": self.urgent,
            "encoded": self.encoded,
            "is_rdr": self.request_delivery_receipt,
            "is_rrr": self.request_read_receipt,
        }


# ----------------------------------------------------------------------
# Adapter
# ----------------------------------------------------------------------
class BBSProtocolAdapter:
    """Protocol behavior wrapper around a BBS profile.

    SendReceiveSession uses this adapter to obtain:
      - The BBS callsign to connect to (bbs_call)
      - Optional TNC init commands (init_commands)
      - Commands for listing and reading inbound messages
      - A send command for outbound messages (build_send_command)
      - Parsers for listing output and full message reads

    Spec support:
      - bind_spec(): bind a BBSSpec to override prompt patterns and parsing rules
      - bind_spec_for_sid_type(): convenience binding by SID type

    Without a spec, parsing falls back to conservative heuristics.
    """

    DEFAULT_PROMPT = ">"

    def __init__(
        self,
        profile: Any,
        *,
        my_calls: Optional[Sequence[str]] = None,
    ) -> None:
        self._p = profile
        self._my_calls = {c.strip().upper() for c in (my_calls or []) if c and c.strip()}

        # Spec support
        self._spec: Optional[BBSSpec] = None
        self._spec_loader = BBSSpecLoader()

        # ---- generic timing / prompt defaults (tune later) ----
        self.connect_success_patterns: List[str] = []   # empty -> don't wait
        self.connect_timeout: float = 8.0

        self.command_prompt: str = self.DEFAULT_PROMPT
        self.command_timeout: float = 10.0

        self.list_complete_prompt: str = self.DEFAULT_PROMPT
        self.read_complete_prompt: str = self.DEFAULT_PROMPT

        # Outbound sending (we’ll refine later)
        self.send_prompt: Optional[str] = None          # None -> don't expect
        self.end_of_message: str = "/EX"
        self.send_success_patterns: List[str] = []      # empty -> don't expect

    # ------------------------------------------------------------------
    # Proxy: anything not explicitly handled falls through to BBSProfile
    # ------------------------------------------------------------------
    def __getattr__(self, name: str):
        """Proxy unknown attributes to the underlying profile object."""
        return getattr(self._p, name)

    # ------------------------------------------------------------------
    # Spec binding
    # ------------------------------------------------------------------
    @property
    def spec(self) -> Optional[BBSSpec]:
        return self._spec

    def bind_spec(self, spec: BBSSpec) -> None:
        """
        Bind a loaded BBSSpec to this adapter.
        This overrides prompt patterns and (optionally) command strings.
        """
        self._spec = spec

        prompt = spec.raw.get("prompt", {}) or {}
        ptn = str(prompt.get("pattern", "")).strip() or self.DEFAULT_PROMPT

        # Use the same prompt pattern for command completion unless spec evolves later
        self.command_prompt = ptn
        self.list_complete_prompt = ptn
        self.read_complete_prompt = ptn

        # Commands (currently we only need LM + R patterns for receive)
        cmds = spec.raw.get("commands", {}) or {}
        lm = str(cmds.get("list_mine", "")).strip()
        if lm:
            # This property is computed; we use this for LM in spec mode
            self._spec_list_mine_cmd = lm
        else:
            self._spec_list_mine_cmd = None

        # Optional: add more spec-bound settings later (timeouts, init, etc.)

    def bind_spec_for_sid_type(self, sid_type: str) -> BBSSpec:
        """
        Load and bind a spec using a SID type identifier.

        Example SID types: "KPC3P", "JNOS", "WL2K".

        Returns:
            The loaded BBSSpec.
        """
        spec = self._spec_loader.load_for_sid_type(sid_type)
        self.bind_spec(spec)
        return spec

    # ------------------------------------------------------------------
    # Commands / init (your existing logic preserved)
    # ------------------------------------------------------------------
    @property
    def bbs_call(self) -> str:
        """Return the remote BBS callsign used for the connect command."""
        # Prefer explicit profile fields if present
        for attr in ("bbs_call", "call", "callsign"):
            v = (getattr(self._p, attr, "") or "").strip()
            if v:
                return v

        # Fall back to connect_call (your previous behavior)
        return (getattr(self._p, "connect_call", "") or "").strip()

    @property
    def init_commands(self) -> List[str]:
        """
        Profile has:
          - use_init_cmd (bool)
          - cmd_before / cmd_after (strings)
        We treat them as a list of commands, split by newline or ';'.
        """
        if not bool(getattr(self._p, "use_init_cmd", False)):
            return []

        cmds: List[str] = []
        for blob in (getattr(self._p, "cmd_before", ""), getattr(self._p, "cmd_after", "")):
            blob = (blob or "").strip()
            if not blob:
                continue
            # split by newline or semicolon; keep order
            parts = []
            for line in blob.splitlines():
                parts.extend([p.strip() for p in line.split(";") if p.strip()])
            cmds.extend(parts)

        return cmds

    @property
    def list_messages_command(self) -> str:
        """
        Return the BBS command used to list messages.

        Priority:
          1) User/profile override (cmd_list_mine/cmd_list_bcast/cmd_list_nts)
          2) Spec default (spec.commands.*)
          3) Hardcoded fallback (LM/LB/LT)
        """

        # Determine which listing we want (private first, Classic-ish)
        want_private = bool(getattr(self._p, "retrieve_private", False))
        want_bull    = bool(getattr(self._p, "retrieve_bulletins", False))
        want_nts     = bool(getattr(self._p, "retrieve_nts", False))

        # -------- 1) profile overrides --------
        if want_private:
            v = (getattr(self._p, "cmd_list_mine", "") or "").strip()
            if v:
                return v
        if want_bull:
            v = (getattr(self._p, "cmd_list_bcast", "") or "").strip()
            if v:
                return v
        if want_nts:
            v = (getattr(self._p, "cmd_list_nts", "") or "").strip()
            if v:
                return v

        # -------- 2) spec defaults --------
        if self._spec is not None:
            cmds = self._spec.raw.get("commands", {}) or {}

            if want_private:
                v = str(cmds.get("list_mine", "")).strip()
                if v:
                    return v

            if want_bull:
                v = str(cmds.get("list_bcast", "")).strip()
                if v:
                    return v

            if want_nts:
                v = str(cmds.get("list_nts", "")).strip()
                if v:
                    return v

        # -------- 3) hardcoded fallbacks --------
        if want_private:
            return "LM"
        if want_bull:
            return "LB"
        if want_nts:
            return "LT"
        return "LM"


    # ------------------------------------------------------------------
    # Listing selection helpers (260115)
    # ------------------------------------------------------------------
    def enabled_categories(self) -> list[str]:
        """ 260115
        Return enabled inbound retrieval categories based on the active BBS profile flags.

        Categories are returned in a stable order:
            PRIVATE, BULLETIN, NTS

        IMPORTANT:
        - We assume the profile stores explicit True/False values.
        - Therefore we default missing flags to False (not True).
        """
        out: list[str] = []
        p = self._p

        if bool(getattr(p, "retrieve_private", False)):
            out.append("PRIVATE")
        if bool(getattr(p, "retrieve_bulletins", False)):
            out.append("BULLETIN")
        if bool(getattr(p, "retrieve_nts", False)):
            out.append("NTS")

        return out


    def list_command_for(self, category: str) -> str:
        """ 260115
        Return the BBS command used to list messages for a given category.

        Priority:
          1) Profile override (cmd_list_mine / cmd_list_bcast / cmd_list_nts)
          2) Spec default     (spec.commands.list_mine / list_bcast / list_nts)
          3) Hardcoded fallback (LM / LB / LT)
        """
        cat = (category or "").strip().upper()
        p = self._p

        # ---------- 1) profile overrides ----------
        if cat == "PRIVATE":
            v = (getattr(p, "cmd_list_mine", "") or "").strip()
            if v:
                return v
        elif cat == "BULLETIN":
            v = (getattr(p, "cmd_list_bcast", "") or "").strip()
            if v:
                return v
        elif cat == "NTS":
            v = (getattr(p, "cmd_list_nts", "") or "").strip()
            if v:
                return v

        # ---------- 2) spec defaults ----------
        if self._spec is not None:
            cmds = self._spec.raw.get("commands", {}) or {}
            if cat == "PRIVATE":
                v = str(cmds.get("list_mine", "")).strip()
                if v:
                    return v
            elif cat == "BULLETIN":
                v = str(cmds.get("list_bcast", "")).strip()
                if v:
                    return v
            elif cat == "NTS":
                v = str(cmds.get("list_nts", "")).strip()
                if v:
                    return v

        # ---------- 3) hardcoded fallbacks ----------
        if cat == "BULLETIN":
            return "LB"
        if cat == "NTS":
            return "LT"
        return "LM"


    def build_send_command(self, msg: Any) -> str:
        """
        Build an SP/SB/ST command based on message type.

        We try to be flexible about outbound msg fields because the outbound model
        may differ slightly across layers (repo/view/legacy).
        """
        to_call = (getattr(msg, "to_call", None) or getattr(msg, "to", None) or "").strip()
        subject = (getattr(msg, "subject", "") or "").strip()

        # Message type hinting
        mtype = getattr(msg, "mtype", None)
        # Some implementations store mtype as int/enum; tolerate both.
        mtype_val = None
        try:
            mtype_val = int(mtype.value) if hasattr(mtype, "value") else int(mtype) if mtype is not None else None
        except Exception:
            mtype_val = None

        if mtype_val == 2:  # Bulletin
            cmd = getattr(self._p, "cmd_send_bcast", "SB") or "SB"
        elif mtype_val == 1:  # NTS
            cmd = getattr(self._p, "cmd_send_nts", "ST") or "ST"
        else:
            cmd = getattr(self._p, "cmd_send_private", "SP") or "SP"

        return f"{cmd} {to_call} {subject}".strip()


    # 260102, add BBS delete command helper
    def build_delete_command(self, msgno: str) -> str:
        """
        Build the delete/kill command for an inbound message number.

        Spec mode:
          uses spec.commands.kill (e.g., "K {msgno}")
        Fallback mode:
          uses profile cmd_kill if present, else "K"
        """
        msgno = str(msgno).strip()
        if not msgno:
            raise ValueError("msgno is empty")

        # Spec mode
        if self._spec is not None:
            cmds = self._spec.raw.get("commands", {}) or {}
            templ = str(cmds.get("kill", "")).strip()
            if templ:
                return templ.format(msgno=msgno)

        # Profile mode fallback
        cmd = (getattr(self._p, "cmd_kill", None) or getattr(self._p, "cmd_delete", None) or "K").strip()
        return f"{cmd} {msgno}".strip()


    # ------------------------------------------------------------------
    # Parsers (spec-driven if bound; else generic fallback)
    # ------------------------------------------------------------------
    _re_list_id = re.compile(r"^\s*(\d+)\b", re.MULTILINE)

    def parse_message_listing(self, listing_text: str) -> List[str]:
        """
        Parse a BBS message listing (LM/LB/LT output) into message numbers.

        Spec mode:
          - Uses spec.list_mine.entry_pattern with named group "msgno"
        Generic mode:
          - Returns all leading integers on lines

        Returns a de-duplicated list preserving order.

        Notes:
        ------
        - This returns only the msgno's.  Callers that need all fields should use
           parse_message_listing_rows().
        """
        if self._spec is None:
            return self._parse_message_listing_generic(listing_text)

        lm = self._spec.raw.get("list_mine", {}) or {}
        entry_pattern = str(lm.get("entry_pattern", "")).strip()
        header_start_pattern = str(lm.get("header_start_pattern", "")).strip()

        if not entry_pattern:
            return self._parse_message_listing_generic(listing_text)

        entry_rx = re.compile(entry_pattern)
        header_rx = re.compile(header_start_pattern) if header_start_pattern else None

        lines = (listing_text or "").splitlines()
        started = header_rx is None

        out: List[str] = []
        for line in lines:
            s = line.rstrip("\r\n")
            if not started:
                if header_rx and header_rx.search(s):
                    started = True
                continue

            m = entry_rx.search(s)
            if not m:
                continue

            msgno = (m.groupdict().get("msgno") or "").strip()
            if msgno:
                out.append(msgno)

        return self._dedupe_preserve_order(out)


    def parse_full_message(self, raw_text: str) -> dict:
        """
        Parse a full message read (R <msgno>) into a normalized dict.

        Spec mode:
          - Uses spec.read_message parsing rules (KPC3-style or JNOS-style)
        Generic mode:
          - Conservative heuristic parser for From/To/Subject + body split
        """
        if self._spec is None:
            return self._parse_full_message_generic(raw_text)

        rm = self._spec.raw.get("read_message", {}) or {}

        # KPC3 spec style: header_line_pattern + subject_pattern
        if "header_line_pattern" in rm:
            parsed = self._parse_kpc3_read(raw_text or "", rm)
            return parsed.to_dict()

        # JNOS spec style: header_patterns dict (+ optional date_parse)
        if "header_patterns" in rm:
            parsed = self._parse_jnos_read(raw_text or "", rm)
            return parsed.to_dict()

        # Unknown spec shape → fallback
        return self._parse_full_message_generic(raw_text)


    def parse_message_listing_rows(self, raw: str) -> list[dict]:
        """
        260113, added
        Parse a BBS message listing into structured row dictionaries.

        This method is the structured counterpart to parse_message_listing().
        Instead of returning only message numbers, it returns one dictionary
        per listing row with named fields extracted from the BBS spec.

        Why this exists (Outpost Classic parity):
        ---------------------------------------
        Some BBS commands (e.g., 'L' = List All) return messages not addressed
        to the local operator. Outpost Classic avoided downloading messages
        not addressed to the user by inspecting the listing and filtering
        before issuing any 'R <msgno>' commands.

        parse_message_listing_rows() enables the same behavior by exposing
        the TO/FROM fields from the listing so the caller can decide which
        messages are eligible for retrieval.

        Behavior:
        ---------
        - Requires a bound BBS spec with a 'list_mine.entry_pattern'.
        - Uses the named capture groups defined in the spec.
        - Returns an empty list if parsing is not possible.

        Args:
            raw: Raw text returned by the BBS after a list command (LM, L, etc.)

        Returns:
            List of dicts, one per parsed listing row.
            Each dict contains at least:
                {
                    "msgno":  str,
                    "to":     str,
                    "from":   str,
                    "subject": str,
                    "status": str,
                    "size":   str,
                    "date":   str,
                    "time":   str,
                }

            Additional fields may be present depending on the spec.

        Notes:
        ------
        - This method does NOT decide which messages to retrieve.
          That policy belongs in SendReceiveSession.
        - Callers that only need message numbers should continue
          to use parse_message_listing().
        """
        if not self._spec:
            return []

        list_cfg = self._spec.raw.get("list_mine", {}) or {}
        entry_pat = list_cfg.get("entry_pattern")
        if not entry_pat:
            return []

        flags = re.MULTILINE
        rx = re.compile(entry_pat, flags)

        rows: list[dict] = []
        for m in rx.finditer(raw):
            row = {k: (v or "").strip() for k, v in m.groupdict().items()}
            if row.get("msgno"):
                rows.append(row)

        return rows

    # ------------------------------------------------------------------
    # Generic fallback logic (your existing approach, preserved)
    # ------------------------------------------------------------------
    def _parse_message_listing_generic(self, listing_text: str) -> List[str]:
        """Generic listing parser: return leading integers for each line."""
        if not listing_text:
            return []
        ids = self._re_list_id.findall(listing_text)
        return self._dedupe_preserve_order(ids)

    def _parse_full_message_generic(self, raw_text: str) -> dict:
        """
        Generic full-message parser: split header/body and extract common fields.
        Covers BPQ
        """
        raw_text = raw_text or ""
        header, body = self._split_header_body(raw_text)

        from_call = self._find_field(header, ("From:", "FROM:", "From "))
        to_call = self._find_field(header, ("To:", "TO:", "To "))
        subject = self._find_field(header, ("Subject:", "SUBJECT:", "Subj:", "SUBJ:", "Title:", "TITLE:"))

        if not subject:
            m = re.search(r"\bSUBJECT\b\s*[:=]\s*(.+)$", header, flags=re.IGNORECASE | re.MULTILINE)
            if m:
                subject = m.group(1).strip()

        sent_at = ""
        m_dt = re.search(
            r"^\s*Date/Time:\s*(?P<sent_at>.+?)\s*$",
            header,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if m_dt:
            sent_at = (m_dt.group("sent_at") or "").strip()

        parsed = ParsedInboundMessage(
            bbs_call=self.bbs_call,
            bbsmsgno="",
            from_call=from_call,
            to_call=to_call,
            subject=subject,
            header=header.strip() if header.strip() else None,
            body=body,
            sent_at=sent_at or None,
        )
        return parsed.to_dict()

    # ------------------------------------------------------------------
    # Spec-driven parsers
    # ------------------------------------------------------------------
    def _parse_kpc3_read(self, raw_text: str, rm: Dict[str, Any]) -> ParsedInboundMessage:
        """Parse a KPC3-style R output using spec patterns."""
        header_line_pattern = str(rm.get("header_line_pattern", "")).strip()
        subject_pattern = str(rm.get("subject_pattern", "")).strip()
        body_start_after_blank = bool(rm.get("body_start_after_blank", True))

        header_rx = re.compile(header_line_pattern) if header_line_pattern else None
        subj_rx = re.compile(subject_pattern) if subject_pattern else None

        lines = (raw_text or "").splitlines()

        header_parts: List[str] = []
        msgno = ""
        from_call = ""
        to_call = ""
        subject = ""
        sent_at_iso: Optional[str] = None

        in_body = False
        body_lines: List[str] = []

        for line in lines:
            s = line.rstrip("\r\n")

            if not in_body:
                header_parts.append(s)

                if header_rx:
                    m = header_rx.search(s)
                    if m:
                        gd = m.groupdict()
                        msgno = (gd.get("msgno") or "").strip()
                        from_call = (gd.get("from") or "").strip()
                        to_call = (gd.get("to") or "").strip()

                        d = (gd.get("date") or "").strip()
                        t = (gd.get("time") or "").strip()
                        fmt = rm.get("datetime_format")
                        if fmt and d and t:
                            try:
                                dt = datetime.strptime(f"{d} {t}", fmt)
                                sent_at_iso = dt.strftime("%Y-%m-%dT%H:%M:%S")
                            except Exception:
                                sent_at_iso = None

                if subj_rx:
                    m2 = subj_rx.search(s)
                    if m2:
                        subject = (m2.groupdict().get("subject") or "").strip()

                if s.strip() == "" and body_start_after_blank:
                    in_body = True
                continue

            body_lines.append(s)

        header_text = "\n".join(header_parts).strip("\n")
        body_text = "\n".join(body_lines).strip("\n")

        return ParsedInboundMessage(
            bbs_call=self.bbs_call,
            bbsmsgno=msgno,
            from_call=from_call,
            to_call=to_call,
            subject=subject,
            header=header_text if header_text else None,
            body=body_text,
            sent_at=sent_at_iso,
        )

    def _parse_jnos_read(self, raw_text: str, rm: Dict[str, Any]) -> ParsedInboundMessage:
        """Parse a JNOS-style R output using spec patterns."""
        header_patterns = rm.get("header_patterns", {}) or {}
        body_start_after_blank = bool(rm.get("body_start_after_blank", True))

        rx_date = re.compile(str(header_patterns.get("date", "")).strip()) if header_patterns.get("date") else None
        rx_from = re.compile(str(header_patterns.get("from", "")).strip()) if header_patterns.get("from") else None
        rx_to = re.compile(str(header_patterns.get("to", "")).strip()) if header_patterns.get("to") else None
        rx_cc = re.compile(str(header_patterns.get("cc", "")).strip()) if header_patterns.get("cc") else None
        cc_call = ""
        rx_subj = re.compile(str(header_patterns.get("subject", "")).strip()) if header_patterns.get("subject") else None

        rx_msgno = re.compile(r"Message\s+#(?P<msgno>\d+)", re.IGNORECASE)

        date_parse = rm.get("date_parse", {}) or {}
        date_parse_pattern = str(date_parse.get("pattern", "")).strip()

        lines = (raw_text or "").splitlines()

        header_parts: List[str] = []
        body_lines: List[str] = []

        msgno = ""
        from_call = ""
        to_call = ""
        subject = ""
        sent_at_iso: Optional[str] = None

        in_body = False
        for line in lines:
            s = line.rstrip("\r\n")

            if not in_body:
                header_parts.append(s)

                m0 = rx_msgno.search(s)
                if m0 and not msgno:
                    msgno = (m0.groupdict().get("msgno") or "").strip()

                if rx_date:
                    m = rx_date.search(s)
                    if m:
                        date_text = (m.groupdict().get("date") or "").strip()
                        sent_at_iso = self._jnos_date_to_iso(date_text, date_parse_pattern)

                if rx_from:
                    m = rx_from.search(s)
                    if m:
                        from_call = (m.groupdict().get("from") or "").strip()

                if rx_to:
                    m = rx_to.search(s)
                    if m:
                        to_call = (m.groupdict().get("to") or "").strip()

                if rx_cc:
                    m = rx_cc.search(s)
                    if m:
                        cc_call = (m.groupdict().get("cc") or "").strip()

                if rx_subj:
                    m = rx_subj.search(s)
                    if m:
                        subject = (m.groupdict().get("subject") or "").strip()

                if s.strip() == "" and body_start_after_blank:
                    in_body = True
                continue

            body_lines.append(s)

        header_text = "\n".join(header_parts).strip("\n")
        body_text = "\n".join(body_lines).strip("\n")

        if cc_call:
            if to_call:
                to_call = f"{to_call};{cc_call}"
            else:
                to_call = cc_call

        return ParsedInboundMessage(
            bbs_call=self.bbs_call,
            bbsmsgno=msgno,
            from_call=from_call,
            to_call=to_call,
            subject=subject,
            header=header_text if header_text else None,
            body=body_text,
            sent_at=sent_at_iso,
        )

    def _jnos_date_to_iso(self, date_text: str, pattern: str) -> Optional[str]:
        """
        Convert a JNOS Date: line into an ISO timestamp using a spec regex.

        The spec regex must expose named groups: day, month (abbr), year,
        hour, minute, second.
        """
        if not date_text or not pattern:
            return None
        rx = re.compile(pattern)
        m = rx.search(date_text)
        if not m:
            return None

        gd = m.groupdict()
        try:
            day = int(gd["day"])
            year = int(gd["year"])
            hour = int(gd["hour"])
            minute = int(gd["minute"])
            second = int(gd["second"])
            mon_str = gd["month"]
            month = datetime.strptime(mon_str, "%b").month
            dt = datetime(year, month, day, hour, minute, second)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _dedupe_preserve_order(items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for s in items:
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    @staticmethod
    def _split_header_body(raw: str) -> tuple[str, str]:
        m = re.search(r"\n\s*\n", raw)
        if not m:
            return raw, ""
        idx = m.start()
        header = raw[:idx]
        body = raw[m.end():]
        return header, body

    @staticmethod
    def _find_field(text: str, prefixes: Sequence[str]) -> str:
        for pfx in prefixes:
            m = re.search(rf"^{re.escape(pfx)}\s*(.+)$", text, flags=re.MULTILINE)
            if m:
                return m.group(1).strip()
        return ""
