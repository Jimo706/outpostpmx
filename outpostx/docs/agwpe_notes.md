# AGWPE Integration Notes

**Project:** OutpostX\
**Author:** Jim Oberhofer

------------------------------------------------------------------------

## 1. Overview

AGWPE (SV2AGW Packet Engine) provides a shared interface between packet
radio applications and TNC hardware or soundcard‑based modems.

Instead of communicating directly with a serial TNC, an application
connects to AGWPE via a **TCP socket** and exchanges framed binary
messages.

This allows:

-   Multiple applications to share the same radio modem
-   Software modems using the PC soundcard
-   Easier integration with Windows packet radio software

OutpostX supports AGWPE alongside:

-   Serial TNC (TAPR / SCS)
-   TELNET BBS access
-   AGWPE packet interface

------------------------------------------------------------------------

## 2. Default Connection

Typical AGWPE connection parameters:

    Host: 127.0.0.1
    Port: 8000

Sequence used by OutpostX:

1.  TCP connect
2.  Optional AGWPE login
3.  Register callsign
4.  Connect to BBS
5.  Exchange packet data
6.  Disconnect and unregister

------------------------------------------------------------------------

## 3. Implementation Location

>    transports/agw_connection.py

Primary class:

>    AGWConnection(BaseConnection)

Responsibilities:

-   Establish TCP connection
-   Build AGWPE frames
-   Parse received frames
-   Maintain session state
-   Forward text to the session adapter

------------------------------------------------------------------------

## 4. AGWPE Frame Structure

Each frame contains:

>    36 byte header +  variable length payload

Important header fields:

    Offset   Field             Description
    -------- ----------------- ----------------------
    0        Port              Radio port
    4        DataKind          Frame type
    6        PID               Protocol ID
    8--18    From Call         Source callsign
    18--28   To Call           Destination callsign
    28--30   Length (16‑bit)   
    32--36   Length (32‑bit)   

OutpostX writes both length fields for compatibility with various AGWPE
implementations.

------------------------------------------------------------------------

## 5. Frame Types Used

    Kind   Purpose
    ------ -------------------------
    P      Remote login
    X      Register callsign
    x      Unregister callsign
    C      Connect to station
    v      Connect via digipeaters
    d      Disconnect
    D      Connected data
    M      Unproto transmission

------------------------------------------------------------------------

## 6. Session Flow

    Start
     ↓
    TCP Connect
     ↓
    Register Callsign
     ↓
    Connect to BBS
     ↓
    Send / Receive Messages
     ↓
    Disconnect
     ↓
    Unregister
     ↓
    Close Socket

------------------------------------------------------------------------

## 7. Radio Port Mapping

AGWPE ports are **0‑based internally**.

Example:

    Radio Port = 1 → port_out = 0
    Radio Port = 2 → port_out = 1
    Radio Port = 3 → port_out = 2

------------------------------------------------------------------------

## 8. Digipeater Paths

AGWPE requires digipeater paths encoded as:

    Byte 0 = hop count
    Followed by N digipeater calls (10 bytes each)

Example:

>    ["K6XYZ-1", "WIDE2-1"]

Payload:

>    02
>    K6XYZ-1
>    WIDE2-1

------------------------------------------------------------------------

## 9. Registration

AGWPE requires applications to **register a callsign** before
connecting.

Frame:

>    DataKind = X

Server response:

>    0x01 = success\
>    0x00 = failure

OutpostX waits for confirmation before continuing.

------------------------------------------------------------------------

## 10. Error Conditions

Typical errors include:

    Condition              Cause
    ---------------------- -----------------------------
    Registration failure   Callsign already registered
    Socket failure         AGWPE not running
    Timeout                RF link issues
    Disconnect             Link drop

------------------------------------------------------------------------

## 11. Design Notes

Key design decisions:

### Transport Abstraction

AGWPE integrates with the same interface used by:

-   Serial TNC
-   TELNET

### Adapter Pattern

AGWConnection communicates through:

    SendReceiveAdapter

which handles:

-   transcript logging
-   buffered receive
-   prompt detection

------------------------------------------------------------------------

## 12. Future Enhancements

Potential improvements:

-   Monitor mode support
-   Multiple radio ports
-   Node path support (KA‑Node / NETROM)
-   Improved debugging tools

------------------------------------------------------------------------

### End of Document
