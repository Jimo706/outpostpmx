# OutpostX Documentation

Welcome to the documentation for **OutpostX**, the next-generation packet BBS messaging client designed to continue the legacy of **Outpost Packet Message Manager**.

OutpostX is a cross-platform packet messaging application used primarily within amateur radio packet networks and emergency communications environments.

---

# Documentation Overview

The following documents describe the architecture, operation, and design of the OutpostX system.

| Document | Description |
|--------|-------------|
| [Architecture Overview](architecture.md) | High-level architecture of the OutpostX system |
| [Send/Receive Flow](send_receive_flow.md) | Detailed description of the Send/Receive session lifecycle |
| [AGWPE Transport Notes](agwpe_notes.md) | Implementation details for AGWPE transport support |
| [BBS Protocol Specification System](bbs_protocol_specs.md) | Description of the JSON-based BBS protocol system |

---

# System Overview

OutpostX is organized into several major subsystems:

    UI (PyQt6)
     ↓
    SendReceiveSession
     ↓
    SendReceiveAdapter
     ↓
    Transport Layer
     ├── SerialConnection
     ├── TcpConnection
     └── AGWConnection
     ↓
    BBS Protocol Adapter
     ↓
    JSON BBS Specifications
     ↓
    SQLite Message Database


This architecture provides:

- **Transport independence**
- **Protocol flexibility**
- **Cross-platform operation**
- **Extensibility for new BBS types**

---

# Major Components

### Session Engine
The session engine manages complete send/receive cycles.

Responsibilities include:

- connecting to BBS systems
- sending outbound messages
- retrieving inbound messages
- logging session activity

---

### Transport Layer

OutpostX supports multiple connection types:

| Transport | Description |
|--------|-------------|
| Serial TNC | Direct connection to hardware TNC |
| TELNET | Internet BBS connections |
| AGWPE | Packet Engine interface |

---

### Protocol System

Different packet BBS systems have different behaviors.

OutpostX uses a **spec-driven protocol system** to support multiple BBS types without modifying the core application code.

Supported systems currently include:

- JNOS
- KPC3 PBBS
- Winlink

Future support:

- BPQMailChat

---

# Documentation Structure

    docs/
    ├── index.md
    ├── architecture.md
    ├── send_receive_flow.md
    ├── agwpe_notes.md
    └── bbs_protocol_specs.md


---

# Additional Resources

Project repository:      https://github.com/<yourusername>/OutpostX\
Project website:         https://www.outpostpm.org


---

# Author

Jim Oberhofer  
Author of **Outpost Packet Message Manager**

---

# Status

OutpostX is currently under active development.

Current development priorities include:

- AGWPE transport support
- BPQMailChat integration
- Winlink BBS support
- cross-platform build packaging

---

End of Document