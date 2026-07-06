# data/bbs_profile_model.py
"""
BBS profile model.

This module defines the BBSProfile dataclass, which represents a complete
configuration for interacting with a specific Bulletin Board System (BBS).

Architectural role:
- Persistence and transport-neutral data model.
- Stored by BBSProfileDAO and managed by BBSProfileRepository.
- Consumed by SendReceiveSession and BBSProtocolAdapter to construct
  connect, list, read, send, and disconnect commands.

Conceptually, a BBSProfile answers:
- *Who* do I connect to? (connect_call, interface_name)
- *How* do I talk to it? (command vocabulary)
- *What* do I retrieve or skip? (retrieve / skip flags)
- *How* do I route packets? (DIRECT / VIA / NODE path settings)

Normalization:
- Callsigns and command strings are typically uppercased by the UI or DAO.
- Boolean values are stored as Python bools and mapped to INTEGER 0/1 in SQLite.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BBSProfile:
    """
    BBS configuration profile.

    Mirrors the BBS data definitions in the OutpostX IRS (section 7.1.1).

    Notes
    -----
    * ``id`` is the SQLite primary key; ``None`` means the profile has not
      yet been inserted.
    * ``friendly_name`` is the human-facing identifier and must be unique.
    * ``interface_name`` currently stores a string reference to an Interface
      profile. This may become a foreign key in a future schema revision.
    * Command fields (SP/LB/R/etc.) are stored explicitly to support
      non-standard or legacy BBS implementations.
    * Path settings define *how the connect command is built*; NODE paths
      are stored separately and referenced indirectly.
    """

    id: Optional[int] = None

    # Basics
    friendly_name: str = ""
    bbs_call: str = ""
    connect_call: str = ""
    description: str = ""
    interface_name: str = ""

    # BBS Commands
    cmd_send_private: str = "SP"
    cmd_send_bcast: str = "SB"
    cmd_send_nts: str = "ST"
    cmd_list_mine: str = "LM"
    cmd_list_bcast: str = "LB"
    cmd_list_nts: str = "LT"
    cmd_list_filtered: str = "L>"
    cmd_read_msg: str = "R"
    cmd_kill_msg: str = "K"
    cmd_bye: str = "B"

    # Init / session commands
    use_init_cmd: bool = False
    cmd_before: str = ""
    cmd_after: str = ""

    # Retrieve options
    retrieve_private: bool = True
    retrieve_nts: bool = False
    retrieve_bulletins: bool = False
    delete_on_bbs: bool = True

    skip_my_nts: bool = False
    skip_my_bulletins: bool = False

    # Bulletins mode: ALL / SELECTED / CUSTOM
    retrieve_bulletins_mode: str = "ALL"
    retrieve_selected: str = ""
    retrieve_custom: str = ""

    retrieve_my_bulletins: bool = False
    retrieve_my_nts: bool = False

    # Path options
    path_type: str = "DIRECT"   # DIRECT, VIA, SCRIPT
    path_via: str = ""          # generic path string
    digipeater_list: str = ""   # explicit digipeater list, if used
    path_script: str = ""       # 260419: explicit script multi-line string
    path_script_timeout: str = "" # 260419: timeout value in seconds

    # Meta
    is_active: bool = False
