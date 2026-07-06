# Changelog
All notable changes to **opxterm** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

DEFINITIONS
ADDED:  Use for new functionality or capability that didn’t exist before; something a user couldn’t do in the previous version.
CHANGE:  Use when altering existing behavior — it’s the same feature, but now behaves differently, is implemented differently, or has a revised interface.
FIXED:  Use for anything where unintended behavior is corrected — i.e., a bug, glitch, or mistake that prevented something from working as designed.

---

## [Unreleased]
### Added
- Initial draft of `CHANGES.md` for tracking releases and updates.

### Changed
- Placeholder section for upcoming work (to be updated before next release).

### Fixed
- Placeholder section for bugfixes.

---

## [0.0.7] - 2025-09-14
### Added
- 250914: SerialConnection: blocking-thread implementation with docstrings, error handling, and consistent UTF-8 encoding.
- 250914: TcpConnection: converted to blocking-thread model to match Serial; added docstrings, CR/CRLF handling option, and clean shutdown.
- 250916: SSHConnection: Paramiko-based blocking-thread implementation with docstrings, adapter guards, and improved disconnect handling.
- 250916: AGWPEConnection: blocking-thread implementation with docstrings, length-field compatibility (16-bit + 32-bit), robust frame parsing, and correct pattern matching.
- 250916: Added consistent `connect() -> bool`, `send()`, `receive()`, and `disconnect()` APIs across all connection types.
- 250916: Added all parameters to call AGWPE in main_opterm, connection_factory, pref_dialog, pref_dialog_ui.py and agwpe_connections
- 250916: Added cut/copy/paste/SelectAll/Clear
- 250918: Added AGWPE handling for via for BBS Connect
- 250925: Added Most Recent Configuration (MRC) for connections
- 251003: Added KISS-Off routine for Kantronics/PacComm TNCs
- 251004: Added validate_config() to ensure all connection fields are set
- 251005: Added geometry save/restore for main windows
- 251005: Added Ctrl+C menu option to return to converse mode

### Changed
- Unified error reporting: background threads emit errors via adapter instead of raising.
- Normalized decode/encode behavior across all transports (`utf-8` with `errors="replace"`).
- Standardized disconnect messages (`[Disconnected] TYPE`).
- 250922: Moved serial, agwpe, and telnet from main to adapter; serial and telnet tested working.
- 250922: Moved ssh from main to adapter; ssh tested working, but some ctrl char echo problems persist.
- 251004: Changed appconfig to share a single instance across main and dialog
- 251004: Changed preferences to update shared self.ini instead of reloading

### Fixed
- TCP: replaced “Telnet” disconnect message with `[Disconnected] TCP`.
- AGWPE: fixed `match` patterns (`'D' | 'C'` instead of `['D','C']`).
- AGWPE: corrected frame processing loop to avoid dropping frames when multiple are buffered.
- perf_dialog.py, dealing with incorrect handling of ini False values, added helper to_bool(..)
- 250915: AGWPE: Working for BBS connects
- 250916: AGWPE: incorrect handling of ini variables, blocked is_registered 0x01 (non-printable) character

---

## [0.0.1] - 2025-08-01
### Added
- Project initialized (`opxterm` base structure).
- Basic GUI shell and configuration system.
- Early TCP/Serial prototypes without docstrings or consistent error handling.

---

## [26.5.2] - 2026-06-22
### Fixed
- PyQt5 → PySide6 migration essentially complete
- terminal-style command entry behavior working
- multiline paste working correctly
- raw Ctrl-character passthrough working
- package structure significantly improved
- assets handling cleaned up
- OpTermX architecture now much closer to OutpostX quality