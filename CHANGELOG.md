# CHANGELOG

All notable changes to the **OutpostX Suite** are documented in this file.

The OutpostX Suite includes:

* **OutpostX** — Packet Message Manager
* **OpTermX** — Communications Terminal

This changelog records significant user-visible features and milestones rather than individual bug fixes or internal development changes.

Version numbering follows the format:

**YYYY.MM.Revision**

Example:

```
2026.07.0
```

---

# Suite 2026.07.0

Included Applications

    | Application | Version   |
    |-------------|-----------|
    | OutpostX    | 2026.07.0 |
    | OpTermX     | 2026.07.0 |

Maintenance Release

### OpTermX (2026.07.0)

#### Changed

- Fixed TELNET initialization issue.
- Corrected configuration parsing using getint().

---

# Suite 2026.07.0

Included Applications

    | Application | Version   |
    |-------------|-----------|
    | OutpostX    | 2026.07.0 |
    | OpTermX     | 2026.07.0 |

First Public Beta

This release marks the first public beta of the modern **OutpostX Suite**, a complete cross-platform redesign of the original Outpost Packet Message Manager.

The suite introduces native support for Windows, Linux, macOS, and Raspberry Pi OS while preserving the familiar operating workflow that Amateur Radio operators have relied upon for more than two decades.

---

### OutpostX

#### Added

* Cross-platform Packet Message Manager
* SQLite message database
* Modern Qt user interface
* Message composition and editing
* Message preview pane
* Folder-based message management
* Printing and print preview
* Import/Export framework
* Profile-based configuration management
* Multiple Station, Tactical, BBS, and Interface profiles
* Automatic Send/Receive scheduling
* Send/Receive session window
* Session transcript logging
* Notification Center
* Status bar with active configuration and session countdown
* Most Recently Used (MRU) configuration selection
* Cross-platform application settings persistence

#### Communications

* Serial TNC support
* TELNET support
* AGWPE support

#### Supported BBS Systems

* JNOS
* BPQ
* KPC3 PBBS
* Winlink CMS (TELNET)

#### Architecture

* SQLite-based message storage
* JSON-driven BBS protocol specifications
* Service-oriented application architecture
* Cross-platform data directory architecture
* Shared application services
* Cross-platform resource management

---

### OpTermX

#### Added

* Cross-platform communications terminal
* Serial communications
* AGWPE client
* TELNET client
* SSH client
* Session logging
* Multiple saved connection profiles
* User-configurable Hot Key profiles
* Modern Qt user interface

---

### Shared

#### Added

* Common OutpostX Suite architecture
* Shared AppPaths framework
* Shared application configuration model
* Shared logging framework
* Shared bootstrap configuration (Opx.conf)
* Cross-platform packaging using PyInstaller
* Common resource management
* Shared data directory policy

#### Platform Support

* Windows 10/11
* Ubuntu Linux
* Raspberry Pi OS (64-bit)
* macOS (Intel)

---

### Future Development

Development continues in the following areas:

* Additional BBS protocol specifications
* Expanded transport support
* Additional message forms
* Enhanced automation
* Additional OutpostX Suite applications
* Expanded documentation
* Native installers for supported platforms
