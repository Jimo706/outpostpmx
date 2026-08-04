# OutpostX Suite
revised: 260803

*A cross-platform communications suite for Amateur Radio Packet
Operations*

The **OutpostX Suite** is a family of modern, cross-platform 
applications designed for Amateur Radio packet communications, emergency 
communications, and bulletin board system (BBS) messaging.

**Design Philosophy**

The suite continues the legacy of **Outpost Packet Message Manager**, while 
introducing a modern architecture that supports Windows, Linux, and macOS.  It 
is designed to preserve the familiar operating workflow of Outpost 'Classic' while 
providing a modern, maintainable, and cross-platform codebase. Rather than simply 
reproducing legacy software, the project emphasizes modular design, file-driven 
protocol definitions, shared services, and long-term extensibility. The goal is 
software that will continue to serve Amateur Radio packet operators for years to come.

------------------------------------------------------------------------

## Applications

### OutpostX

**Packet Message Manager**

OutpostX manages message databases, packet forms, bulletins, NTS
traffic, and Send/Receive sessions with packet BBS systems.

Features include:

-   SQLite message database
-   Packet BBS message management
-   Message composition and editing
-   Send/Receive automation
-   Multiple configuration profiles
-   Session logging
-   Notification center
-   Printing and exporting

Supported transports:

-   Serial TNC
-   TELNET
-   AGWPE

------------------------------------------------------------------------

### OpTermX

**Communications Terminal**

OpTermX is a modern communications terminal for packet radio and related
communications interfaces.

Features include:

-   Serial terminal
-   TELNET client
-   AGWPE support
-   SSH client
-   Session logging
-   Macro/Hot Key profiles
-   Multiple saved configurations
-   Cross-platform operation

OpTermX can be used independently or together with OutpostX.

------------------------------------------------------------------------

## Shared Technologies

Both applications share a common design philosophy, including:

-   Python
-   Qt (PySide6)
-   SQLite
-   Shared configuration architecture
-   Common data directory policy
-   Shared resource management
-   Cross-platform packaging

------------------------------------------------------------------------

## Platform Support

    Operating System   Status
    ----------------   -----------
    Windows 10/11         ✅
    Ubuntu Linux          ✅
    Raspberry Pi OS       ✅
    macOS Intel           ✅
    openSUSE 16.0 Leap    ✅
    macOS Apple Silicon   Coming Soon

------------------------------------------------------------------------

## Current Status

The suite is currently in active beta development.

-   Windows builds complete
-   Linux builds complete
-   macOS builds complete
-   Raspberry Pi builds complete
-   Cross-platform packaging operational

Current work includes:

-   Documentation
-   Beta Testing
-   OptermX expansion
-   Additional BBS protocol support

------------------------------------------------------------------------

## BBS Support

OutpostX uses JSON-based protocol specifications that separate BBS behavior 
from application code. Supporting a new BBS often requires only a new 
specification file rather than modifying the application itself.

-   JNOS
-   BPQ
-   KPC3 PBBS
-   Winlink CMS (Telnet)

**Planned**

-   FBB
-   Winlink RMS (Serial)
-   Additional BBS variants through specification files

------------------------------------------------------------------------

## Documentation

Planned documentation includes:

-   Getting Started
-   Installation
-   Building from Source
-   Data Directory Policy
-   Application Architecture
-   OutpostX User Guide
-   OpTermX User Guide

------------------------------------------------------------------------

## Future Applications

The OutpostX Suite has been designed to support additional applications
in the future, including:

-   OpxScripts
-   ICS 213 Message Maker
-   ICS 309 Message Reporting
-   NTS Message Maker
-   Additional communications tools

------------------------------------------------------------------------

## History

OutpostX is the successor to the original **Outpost Packet Message Manager**, first developed in 2003.

For more than two decades, Outpost has supported Amateur Radio operators
involved in:

-   Emergency Communications
-   ARES®
-   RACES
-   Public Service Events
-   Packet Bulletin Board System Access

The OutpostX Suite preserves that operational heritage while providing a
modern, cross-platform implementation.

------------------------------------------------------------------------

## Author

**Jim Oberhofer KN6PE**

Author of Outpost Packet Message Manager

Website:

https://www.outpostpm.org

------------------------------------------------------------------------

## License

See LICENSE.md for licensing information.

------------------------------------------------------------------------

## Contributing

See CONTRIBUTING.md for development guidelines and contribution information.
