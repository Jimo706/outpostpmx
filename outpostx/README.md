<p align="center">
<img src="docs/images/outpostx_banner.svg" width="900">
</p>

# OutpostX

**Next-Generation Packet BBS Messaging Client**

OutpostX is a modern, cross-platform packet BBS client designed to continue the legacy of Outpost Packet Message Manager, widely used in amateur radio emergency communications.

OutpostX provides a graphical interface for sending and receiving packet radio messages through BBS systems using multiple transport interfaces including serial TNCs, TELNET, and AGWPE.

The goal of OutpostX is to preserve the operational workflow of Outpost Classic while modernizing the codebase for reliability, maintainability, and cross-platform operation.

## Key Features
### Packet BBS Messaging

Send and receive messages through packet radio bulletin board systems.

Supported message types include:

- Personal messages
- Bulletins
- NTS traffic

### Multiple Transport Interfaces

OutpostX supports several connection methods:

    Interface   Description
    ----------  --------------------------------- 
    Serial TNC  Direct connection to hardware TNC
    TELNET      Internet access to BBS servers
    AGWPE       Packet Engine interface

The session engine treats transports uniformly, allowing the same workflow across all interfaces.

### Cross Platform

OutpostX runs on:
- Windows
- Linux
- macOS

Built using:
- Python
- PyQt6

### Spec-Driven BBS Protocol System

Different packet BBS systems behave differently.
OutpostX solves this using a JSON-based protocol specification system.

Supported BBS types currently include:
- JNOS
- KPC3 PBBS

Planned support:
- BPQMailChat
- Winlink BBS

Adding a new BBS type typically requires only a JSON spec file, not code changes.

### Reliable Send/Receive Sessions

The Send/Receive engine:
- logs into the BBS
- sends outbound messages
- retrieves inbound messages
- logs out cleanly

The workflow emulates how a human operator interacts with a packet BBS.

## Architecture Overview

OutpostX uses a layered architecture that separates UI, session logic, transports, and protocol parsing.

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

This architecture allows:

- transport independence
- protocol flexibility
- easier testing
- easier addition of new BBS types

## Screenshots

(Screenshots will be added as development progresses.)

Typical screens include:
- Message list view
- Send/Receive session window
- BBS transcript window
- Configuration dialogs

Example placeholders:

    docs/images/main_window.png
    docs/images/send_receive_dialog.png

## Repository Structure

    OutpostX
    │
    ├── data
    │   └── bbs_specs
    ├── dialogs
    ├── services
    ├── transports
    │   └── adapters
    ├── ui
    ├── widgets
    │
    ├── docs
    │   ├── architecture.md
    │   ├── send_receive_flow.md
    │   ├── agwpe_notes.md
    │   └── bbs_protocol_specs.md
    │
    ├── main.py
    └── README.md

## Installation (Development)

Clone the repository:

    git clone https://github.com/<username>/OutpostX.git
    cd OutpostX

Create a virtual environment:

    python -m venv venv

Activate the environment - Windows:

    venv\Scripts\activate   

Activate the environment - Linux / Mac:

    source venv/bin/activate

Install dependencies:

    pip install -r requirements.txt

Run the application:

    python main.py

## Documentation

Detailed documentation is available in the docs directory.

    Document	            Description
    ----------------------  ------------------------------ 
    architecture.md	        System architecture overview
    send_receive_flow.md	Send/Receive session lifecycle
    agwpe_notes.md	        AGWPE transport implementation
    bbs_protocol_specs.md	JSON protocol spec system

Project documentation is available here:  [OutpostX Documentation](docs/index.md)

## Project History

OutpostX is the successor to Outpost Packet Message Manager, originally developed beginning in 2003.

Outpost *Classic* became widely used in amateur radio emergency communications groups including:

- ARES
- RACES
- CERT support teams
- General packet BBS users

OutpostX continues this tradition with a modern architecture and cross-platform support.

## Author

Jim Oberhofer\
Author of Outpost Packet Message Manager

### Website:
https://www.outpostpm.org

## Contributing

Contributions are welcome.

Areas of interest include:

- additional BBS protocol specifications
- transport improvements
- UI improvements
- documentation

## License

License information will be added to the repository.

## Acknowledgements
 
Special thanks to the amateur radio packet community and the many Outpost users who have supported packet messaging for emergency communications over the years.

## Status
Active development

Current goals include:

- AGWPE integration
- BPQMailChat support
- Winlink BBS support
- cross-platform build packaging