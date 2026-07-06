# BBS Protocol Specification System
Author: Jim Oberhofer  
Project: OutpostX

---

## 1. Overview

OutpostX supports multiple packet BBS systems including:

- JNOS
- KPC3 PBBS
- Winlink RMS
- BPQMailChat (planned)

Each BBS has subtle differences in:

- command prompts
- message listing formats
- message header formats
- login sequences
- deletion rules

To avoid hard-coding BBS behavior into the program, OutpostX uses a
**data-driven protocol system** based on JSON specification files.

These specification files describe how to interact with each BBS type.

---

## 2. Location of Specification Files

BBS specification files are stored in:

    data/bbs_specs/

Examples:

    kpc3_spec.json
    jnos_spec.json
    wl2k_spec.json

Each file describes the behavior of a specific BBS family.

---

## 3. Spec Loader

Specification files are loaded by:

    services/bbs_spec_loader.py


The loader reads the JSON specification and creates a structure used
by the protocol adapter.

Primary class:

    BbsSpec
---

## 4. Protocol Adapter

The component responsible for interpreting BBS specs is:

    services/bbs_protocol_adapter.py

Responsibilities:

- Send BBS commands defined in the spec
- Parse BBS responses using regex patterns
- Extract message metadata
- Normalize message data for storage

The adapter allows SendReceiveSession to remain **independent of
specific BBS formats**.

---

## 5. Spec File Structure

Each specification file contains several sections.

Typical structure:

    {
    "bbs_type": "JNOS",

    "prompt": {
    "pattern": "\)\s*>$",
    "case_insensitive": true
    },

    "commands": {
    "list_mine": "LM",
    "read_message": "R {msgno}",
    "delete_message": "K {msgno}",
    "bye": "B"
    },

    "list_mine": {
    "header_start_pattern": "^St\.",
    "entry_pattern": "...regex..."
    },

    "read_message": {
    "header_pattern": "...regex..."
    }
    }

---

## 6. Prompt Detection

Each BBS type has a unique command prompt.

Example:

JNOS prompt:

    (#0) >

Regex used in spec:

    )\s*>
The SendReceiveAdapter waits for this prompt before issuing
the next command.

---

## 7. Command Definitions

The `commands` section defines BBS commands used during a session.

Example:

    "commands": {
    "list_mine": "LM",
    "read_message": "R {msgno}",
    "delete_message": "K {msgno}",
    "bye": "B"
    }

These commands are used by the protocol adapter when interacting
with the BBS.

---

## 8. Message Listing Parsing

BBS systems return message listings in different formats.

Example JNOS listing:

    St. To    From  Date  Size Subject
    123 KN6PE W6ABC Jan12 245  Test message

The spec contains a regex pattern to parse each entry.

Example structure:

    "entry_pattern": "(?P<msgno>\d+)\s+(?P<to>\S+)\s+(?P<from>\S+)\s+(?P<date>\S+)\s+(?P<size>\d+)\s+(?P<subject>.*)"

Named capture groups allow the adapter to extract message fields.

---

## 9. Message Header Parsing

When a message is retrieved using:

    R <msgno>

the BBS returns a message header.

Example:

    MSG#136 01/21/07 10:01:43
    FROM W6TDM
    TO KN6PE
    SUBJECT: Test message

The specification includes patterns to extract these fields.

Typical fields:

- message number
- sender callsign
- destination callsign
- timestamp
- subject

---

## 10. Date and Time Handling

Different BBS systems use different date formats.

Examples include:

    Jan12
    01/21/07 10:01:43
    21-Jan-2007
The specification defines which formats may appear.

The protocol adapter converts these values into normalized timestamps.

---

## 11. Duplicate Detection

To avoid downloading the same message multiple times,
OutpostX tracks previously downloaded messages.

Standard BBS systems use stable message numbers.

Example:

    bbs_call + msgno

However, some systems (such as JNOS) use **relative message numbers**
within bulletin areas.

In these cases OutpostX generates a synthetic identifier
based on message metadata.

Example fields used:

    FROM
    TO
    DATE
    SUBJECT
---

## 12. Bulletin Areas

Some BBS systems support bulletin areas.

Example JNOS areas:

    XSCPERM
    XSCEVENT
    ALLXSC

OutpostX can switch areas during a session to retrieve messages.

Example command sequence:

    A XSCPERM
    LA

The spec can define commands used for these operations.

---

## 13. Extending to New BBS Types

To support a new BBS type:

1. Create a new JSON specification file
2. Define prompt pattern
3. Define commands
4. Define listing parser
5. Define message parser

Example:

    bpq_spec.json

No core code changes are required.

---

## 14. Benefits of the Spec System

Advantages of this approach:

### Protocol flexibility

Different BBS formats can be supported easily.

### Reduced code complexity

Protocol differences are isolated in spec files.

### Easier debugging

Regex patterns can be adjusted without modifying program logic.

### Easier community contributions

New BBS specs can be contributed without modifying core code.

---

## 15. Future Enhancements

Possible improvements to the spec system include:

- scriptable login sequences
- area scanning definitions
- BBS capability detection
- optional command overrides

---

### End of Document