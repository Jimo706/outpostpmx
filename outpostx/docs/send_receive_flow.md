
# Send/Receive Session Flow
**Author:** Jim Oberhofer  
**Project:** OutpostX

---

## 1. Overview

The Send/Receive session is the core operational process in OutpostX.

It connects to a BBS, exchanges messages, and terminates the session.

The process is implemented in:

> services/send_receive_session.py

Class:
> SendReceiveSession

---

## 2. Session Lifecycle

A session follows this sequence:

    Start Session
      ↓
    Take configuration snapshot
      ↓
    Open transport connection
      ↓
    Login to BBS
      ↓
    Send outbound messages
      ↓
    Receive inbound messages
      ↓
    Logout from BBS
      ↓
    Close connection
      ↓
    Session complete

---

## 3. Configuration Snapshot

At the start of the session:

> _take_snapshot()

captures:

- active station
- tactical callsign
- interface profile
- BBS profile
- operator identity
- login credentials

This snapshot ensures a stable configuration during the session.

---

## 4. Transport Connection

The connection is opened using:
> _open_connection()

The transport is created through:
> get_connection()

Supported transports:

- Serial TNC
- TELNET
- AGWPE

The transport is wrapped by:
> SendReceiveAdapter

which provides buffered reads and prompt detection.

---

## 5. Login Phase

Login behavior depends on the transport.

### Serial TNC
> _login_bbs_via_tnc()

Steps:

1. Ensure TNC command mode
2. Initialize TNC parameters
3. Issue connect command
4. Wait for BBS prompt
5. Detect BBS SID

---

### TELNET
> _login_bbs_via_telnet()

Steps:

1. Wait for login prompt
2. Send callsign
3. Send password
4. Detect BBS prompt

JNOS and Winlnik secure login are supported.

---

### AGWPE
> _login_bbs_via_agwpe()

Steps:

1. Optional AGWPE login
2. Register callsign
3. Set radio port
4. Connect to BBS
5. Wait for BBS prompt

---

## 6. Sending Outbound Messages

Outbound messages are retrieved from the database.

Criteria:

- Message state = QUEUED
- Direction = OUTBOUND
- Folder = Outbox
- Station matches active station
- BBS matches active BBS

Each message is transmitted using:
> _send_message()

Typical sequence:

> SP \<CALL\><br>
> SUBJECT<br>
> MESSAGE BODY<br>
> /EX

The session waits for the BBS command prompt before continuing.

---

## 7. Receiving Inbound Messages

Inbound retrieval follows this process:

1. Retrieve message listings
2. Parse message identifiers
3. Skip messages already downloaded
4. Retrieve new messages
5. Parse message content
6. Store in database

Example listing commands:
> LM<br>
> LB<br>
> L><br>

Message retrieval command:
> R \<msgid>

---

## 8. Duplicate Detection

Duplicate detection prevents downloading the same message multiple times.

Standard BBS systems use:
> bbs_call + message_number

JNOS requires a synthetic message identifier because
message numbers are relative.

OutpostX generates a hash from:
> FROM
> TO
> DATE
> SUBJECT

---

## 9. Message Deletion

If configured, messages can be deleted from the BBS after download.

Command:
> K <msgid>

Deletion rules depend on message category:

| Category | Delete Allowed |
|----------|----------------|
| PRIVATE  |     Yes        |
| BULLETIN |     No         |
| NTS      |  Conditional   |

---

## 10. Logout Phase

Logout behavior depends on transport.

Typical BBS logout command:
> B

Transport cleanup follows.

---

## 11. Abort Handling

Operators may cancel a session at any time.

Abort behavior includes:

- Sending disconnect commands
- Closing the transport
- Terminating session loops

Abort is designed to emulate Outpost Classic behavior.

---

## 12. Logging

Two logs are generated:
> session log
> transcript log

These logs record:

- commands sent
- responses received
- session events
- errors

---

###  End of Document


