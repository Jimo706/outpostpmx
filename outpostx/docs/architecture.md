# OutpostX Architecture
**Author:** Jim Oberhofer  
**Project:** OutpostX – Next Generation Outpost Packet Message Manager

---

## 1. Overview

OutpostX is a cross-platform packet BBS client designed to replace the
original Outpost Packet Message Manager.

The application provides a graphical environment for sending and receiving
messages through amateur radio packet networks.

Supported transport interfaces include:

- Serial TNC (TAPR / KISS / SCS)
- TELNET BBS access
- AGWPE packet engine interface

The system is designed with **clear separation between UI, protocol logic,
transport layers, and data storage**.

---

# 2. High-Level Architecture

    ┌───────────────────────────────┐
    │            UI Layer           │
    │                               │
    │  PyQt6 dialogs and widgets    │
    │                               │
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │        Session Engine         │
    │                               │
    │   SendReceiveSession          │
    │                               │
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │       Transport Adapter       │
    │                               │
    │    SendReceiveAdapter         │
    │                               │
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │        Transport Layer        │
    │                               │
    │  SerialConnection             │
    │  TcpConnection                │
    │  AGWConnection                │
    │                               │
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │         BBS Protocol          │
    │                               │
    │    BBSProtocolAdapter         │
    │    BBS Spec JSON definitions  │
    │                               │
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │          Data Layer           │
    │                               │
    │  SQLite database              │
    │  Message repository           │
    │                               │
    └───────────────────────────────┘

## 3. Core Components
### 3.1 UI Layer

Location:

ui/
dialogs/
widgets/

Responsibilities:

- User interaction
- Configuration dialogs
- Message display
- Transcript display
- Starting Send/Receive sessions

The UI communicates with the session engine but does not implement
protocol logic.

### 3.2 Session Engine

Location:

services/send_receive_session.py

Class:

SendReceiveSession

Responsibilities:

Execute a full send/receive session
Coordinate transports and protocol adapters
Manage session lifecycle

Typical session flow:

snapshot → connect → login → send outbound → receive inbound → logout → cleanup

The session engine is transport-agnostic.

### 3.3 Transport Adapter

Location:

transports/adapters/send_receive_adapter.py

Responsibilities:

- Buffer incoming data
- Provide expect() prompt detection
- Handle transcript logging
- Normalize send/receive operations

This layer allows the session engine to interact with different
transport types in a consistent way.

### 3.4 Transport Layer

Location:

transports/

Supported transport classes:

**SerialConnection**

Used for traditional hardware TNC connections.

**TcpConnection**

Used for TELNET BBS access.

**AGWConnection**

Used for AGWPE packet engine connections.

AGWPE communication uses framed binary messages over TCP.

### 3.5 BBS Protocol Adapter

Location:

services/bbs_protocol_adapter.py

Responsibilities:

Translate BBS commands
Parse message listings
Parse full messages
Detect BBS prompt patterns

Protocol behavior is defined using **JSON specification files**.

Location:

data/bbs_specs/

Example:

kpc3_spec.json
jnos_spec.json

his allows support for multiple BBS types without modifying core code.

### 3.6 Data Layer

The system stores messages and configuration data using SQLite.

Responsibilities:

- Message storage
- Message state management
- Folder organization
- Duplicate message detection

Repository classes handle database operations.

Example:

MessageRepository
SqliteMessageService

### 4. Configuration System

Configuration is managed by:

SystemConfigService

This service provides:

- Active station
- Active interface
- Active BBS
- Operator identity
- Send/receive preferences

The session engine takes a snapshot of configuration at the beginning
of each session.

This ensures that configuration changes made during a session do not
affect the running session.

## 5. Design Principles
**Transport independence**

Session logic does not depend on specific transport types.

**Protocol abstraction**

BBS protocol details are externalized to JSON specifications.

**Session isolation**

Each Send/Receive run uses a configuration snapshot.

**Cross-platform design**

The application runs on:

- Windows
- Linux
- macOS

## 6. Future Architectural Improvements

Possible future enhancements include:

- Plugin architecture for BBS types
- Advanced scripting for automation
- Improved multi-station support
- Enhanced packet monitoring tools

### End of Document