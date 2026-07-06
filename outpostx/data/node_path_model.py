# data/node_path_model.py
"""
Node path model (KA-NODE / NET/ROM multi-hop routing).

This module defines the in-memory data structures used to describe a multi-hop
NODE path between the local station and a target BBS.

Architectural role:
- Pure data model (no I/O, no database access).
- Persisted by NodePathRepo (normalized tables) or serialized as JSON.
- Consumed by NodePathExecutor to step through each hop during a Send/Receive session.

Conceptually:
- A NodePath is an ordered list of NodeHop objects.
- Each NodeHop describes how to connect from the *current* node to the *next* node.
- Success and failure markers are used to determine whether a connect attempt
  succeeded before moving on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


def _split_lines(s: str) -> List[str]:
    """Split textarea content into non-empty trimmed lines."""
    out: List[str] = []
    for line in (s or "").splitlines():
        t = line.strip()
        if t:
            out.append(t)
    return out


def _join_lines(lines: List[str]) -> str:
    """Join marker lines into a newline-separated textarea string."""
    return "\n".join([l.strip() for l in (lines or []) if (l or "").strip()])


@dataclass
class NodeHop:
    """
    One hop in a KA-NODE / NET/ROM path.

    A NodeHop describes how to move from the current node to the *next* node
    in the path.

    Fields
    ------
    node_name
        Name of the *next* node (e.g. "W6TDM-3").
    connect_cmd
        Command issued at the current node to reach the next hop
        (e.g. "C", "X", "BBS", "CONNECT").
    use_next_name
        If True, append the next hop's node_name to connect_cmd.
        Example: "X W6TDM-3".
    port_num
        Optional port number. A value of 0 means "not used".
    success_markers
        One or more strings indicating a successful connect.
    failure_markers
        One or more strings indicating a failed connect.

    Notes
    -----
    * Marker lists are searched as substrings in inbound text.
    * Normalization uppercases node_name and trims all markers.
    * If use_next_name is True, the executor will append the next hop's node_name to connect_cmd.
      e.g. connect_cmd="X", next node_name="W6TDM-3" -> "X W6TDM-3"
      This matches the examples in the application note.
    """
    node_name: str = ""
    connect_cmd: str = ""                 # command to reach the *next* hop
    use_next_name: bool = True            # append next hop's node name?
    port_num: int = 0                     # optional; 0 means not used
    success_markers: List[str] = field(default_factory=list)
    failure_markers: List[str] = field(default_factory=list)

    def normalize(self) -> None:
        """Normalize fields for comparison and execution."""
        self.node_name = (self.node_name or "").strip().upper()
        self.connect_cmd = (self.connect_cmd or "").strip()
        self.success_markers = [s.strip() for s in self.success_markers if (s or "").strip()]
        self.failure_markers = [s.strip() for s in self.failure_markers if (s or "").strip()]
        if self.port_num is None:
            self.port_num = 0
        try:
            self.port_num = int(self.port_num)
        except Exception:
            self.port_num = 0

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict representation of this hop."""
        self.normalize()
        return {
            "node_name": self.node_name,
            "connect_cmd": self.connect_cmd,
            "use_next_name": bool(self.use_next_name),
            "port_num": int(self.port_num),
            "success_markers": list(self.success_markers),
            "failure_markers": list(self.failure_markers),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "NodeHop":
        """Create a NodeHop from a dict (inverse of to_dict())."""
        hop = NodeHop(
            node_name=(d.get("node_name") or ""),
            connect_cmd=(d.get("connect_cmd") or ""),
            use_next_name=bool(d.get("use_next_name", True)),
            port_num=int(d.get("port_num", 0) or 0),
            success_markers=list(d.get("success_markers") or []),
            failure_markers=list(d.get("failure_markers") or []),
        )
        hop.normalize()
        return hop

    # Convenience helpers for UI textareas
    def success_text(self) -> str:
        """Return success markers as textarea-friendly text."""
        return _join_lines(self.success_markers)

    def failure_text(self) -> str:
        """Return failure markers as textarea-friendly text."""
        return _join_lines(self.failure_markers)

    def set_success_text(self, text: str) -> None:
        """Set success markers from textarea input."""
        self.success_markers = _split_lines(text)

    def set_failure_text(self, text: str) -> None:
        """Set failure markers from textarea input."""
        self.failure_markers = _split_lines(text)


@dataclass
class NodePath:
    """
    A complete multi-hop NODE path to a target BBS.

    The executor walks through each NodeHop in order. The final connect to the
    BBS is typically performed after the last hop using the BBSProfile's
    connect_call (unless overridden).

    Notes
    -----
    * An empty NodePath represents DIRECT routing.
    * Versioning is included in serialized forms for future compatibility.
    """
    hops: List[NodeHop] = field(default_factory=list)
    # Optional: if you want to store BBS connect name here later (vs reading from BBSProfile)
    bbs_connect_call: str = ""

    def normalize(self) -> None:
        """Normalize the path and all contained hops."""
        self.bbs_connect_call = (self.bbs_connect_call or "").strip().upper()
        for h in self.hops:
            h.normalize()

    def is_empty(self) -> bool:
        """Return True if the path contains no hops."""
        return len(self.hops) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict representation of this path."""
        self.normalize()
        return {
            "bbs_connect_call": self.bbs_connect_call,
            "hops": [h.to_dict() for h in self.hops],
            "version": 1,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "NodePath":
        """Create a NodePath from a dict (inverse of to_dict())."""
        hops = [NodeHop.from_dict(x) for x in (d.get("hops") or [])]
        np = NodePath(hops=hops, bbs_connect_call=(d.get("bbs_connect_call") or ""))
        np.normalize()
        return np

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize this path to JSON text."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> "NodePath":
        """Deserialize a NodePath from JSON text."""
        return NodePath.from_dict(json.loads(text))

    @staticmethod
    def json_schema() -> Dict[str, Any]:
        """
        A strict-ish JSON schema for validation + future-proofing.
        """
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "OutpostX NodePath",
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "hops"],
            "properties": {
                "version": {"type": "integer", "const": 1},
                "bbs_connect_call": {"type": "string"},
                "hops": {
                    "type": "array",
                    "minItems": 0,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["node_name", "connect_cmd", "use_next_name", "port_num", "success_markers", "failure_markers"],
                        "properties": {
                            "node_name": {"type": "string"},
                            "connect_cmd": {"type": "string"},
                            "use_next_name": {"type": "boolean"},
                            "port_num": {"type": "integer", "minimum": 0},
                            "success_markers": {"type": "array", "items": {"type": "string"}},
                            "failure_markers": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        }
