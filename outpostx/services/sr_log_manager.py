from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class SessionLogPaths:
    logs_dir: str
    session_path: str
    transcript_path: str

class SRLogManager:
    """
    Write OutpostX Send/Receive logs in two parallel daily files:
      - sessionYYMMDD.log     (high-level narrative)
      - transcriptYYMMDD.log  (raw transcript)
    Each S/R run appends a banner divider to both files.
    """

    def __init__(self, data_dir: str, *, app_title: str, app_version: str, marker: str = "") -> None:
        self._data_dir = data_dir
        self._app_title = app_title
        self._app_version = app_version
        self._marker = marker or ""

        self._paths: Optional[SessionLogPaths] = None
        self._fh_session = None
        self._fh_transcript = None

        self._session_id: Optional[int] = None

    def open_for_session(self, session_id: int, now: Optional[datetime] = None) -> int:
        now = now or datetime.now()
        yymmdd = now.strftime("%y%m%d")

        logs_dir = os.path.join(self._data_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        session_path = os.path.join(logs_dir, f"session{yymmdd}.log")
        transcript_path = os.path.join(logs_dir, f"transcript{yymmdd}.log")
        # print(f"***DEBUG[sr_log_mgr-43]> log dir location in logs dir={logs_dir}")    # sourced from the registry

        self._paths = SessionLogPaths(logs_dir, session_path, transcript_path)
        self._fh_session = open(session_path, "a", encoding="utf-8", newline="\n")
        self._fh_transcript = open(transcript_path, "a", encoding="utf-8", newline="\n")

        self._session_id = session_id
        return session_id

    def write_banner(self, snap, now: Optional[datetime] = None) -> None:
        """
        Write a Classic-style divider banner to BOTH files.
        `snap` is your SessionSnapshot (station/bbs/interface/spec info).
        """
        if not self._fh_session or not self._fh_transcript or self._session_id is None:
            return

        now = now or datetime.now()

        # Example: 15-Dec 14:57:42
        ts = now.strftime("%d-%b %H:%M:%S")

        title = f"{self._app_title} v{self._app_version}"
        sid = f"S/R Session # {self._session_id:05d}"

        line1 = "-" * 51
        line2 = f"{ts}: {title}: {sid}"
        lines = [line1, line2]

        # Optional: snapshot details (best-effort; tolerate missing attrs)
        try:
            st = getattr(snap, "station", None)
            bbs = getattr(snap, "bbs", None)
            iface = getattr(snap, "interface", None)

            station_name = getattr(st, "name", "") or getattr(st, "station_name", "")
            bbs_name = getattr(bbs, "name", "") or getattr(bbs, "profile_name", "")
            iface_name = getattr(iface, "interface_name", "") or getattr(iface, "name", "")

            if station_name:
                lines.append(f"Station: {station_name}")
            if bbs_name:
                lines.append(f"BBS: {bbs_name}")
            if iface_name:
                lines.append(f"Interface: {iface_name}")

            # SID / Spec if available
            sid_type = getattr(bbs, "sid_type", "") if bbs else ""
            spec = getattr(bbs, "spec", None) if bbs else None
            spec_name = getattr(spec, "name", "") if spec else ""
            if sid_type or spec_name:
                lines.append(f"SID: {sid_type}   Spec: {spec_name}")

        except Exception:
            pass

        if self._marker:
            lines.append(f"Marker: {self._marker}")

        lines.append(line1)
        text = "\n".join(lines) + "\n"

        self._fh_session.write(text)
        self._fh_session.flush()

        self._fh_transcript.write(text)
        self._fh_transcript.flush()

    def write_session_line(self, text: str) -> None:
        if not self._fh_session:
            return
        s = (text or "").rstrip("\r\n")
        self._fh_session.write(s + "\n")
        self._fh_session.flush()

    def write_transcript_chunk(self, text: str) -> None:
        if not self._fh_transcript:
            return
        # Write transcript exactly as received so the file matches the UI transcript.
        self._fh_transcript.write(text or "")
        self._fh_transcript.flush()

    def close(self) -> None:
        for fh in (self._fh_session, self._fh_transcript):
            try:
                if fh:
                    fh.flush()
                    fh.close()
            except Exception:
                pass
        self._fh_session = None
        self._fh_transcript = None
        self._paths = None
        self._session_id = None
