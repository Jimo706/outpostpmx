# HOWTO: Setup Development Environment

**Document Version:** 1.0 \
**Last Updated:** 06-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 06-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This document describes the process for preparing a development environment capable of building and maintaining the OutpostPMX Suite.

The objective is to establish a repeatable procedure that can be followed when configuring a new development computer or rebuilding an existing development environment.

Platform-specific installation details are documented separately within the Windows, Linux, and macOS build HOWTO documents.

---

# Document Scope

This document describes the common development environment used by all supported platforms.

It does **not** describe:

* Platform-specific operating system installation.
* Platform-specific package managers.
* PyInstaller build procedures.
* GitHub release procedures.

Those topics are documented in separate HOWTO documents.

---

# Audience

This document is intended for developers and maintainers responsible for building or modifying the OutpostPMX Suite.

---

# Prerequisites

Before beginning:

* Administrative privileges are available.
* Internet connectivity is available.
* A GitHub account has been created.
* Access to the OutpostPMX GitHub repository has been established.

---

# Document Conventions

Throughout this document:

* Commands entered at a command prompt appear in a monospace font.
* File and directory names are shown in monospace.
* Platform-specific notes are identified clearly.
* Repository layouts are illustrated using Unicode tree diagrams.
* Notes identify helpful information.
* Warnings identify operations that could result in unexpected behavior.

---

# Chapter 1 - Development Philosophy

The OutpostPMX Suite is developed using native development environments on each supported operating system.

Current supported development platforms include:

| Platform | Status    |
| -------- | --------- |
| Windows  | Supported |
| Linux    | Supported |
| macOS    | Supported |

Each platform maintains its own Python virtual environment while sharing a common repository structure.

---

# Chapter 2 - Common Development Components

Every development environment should include:

* Git
* Python
* Python virtual environment (venv)
* pip
* PySide6
* PyInstaller
* Paramiko
* PySerial

Additional packages may be required as the project evolves.

---

# Chapter 3 - Repository Layout

The recommended development layout is:

```text
dev/
│
└── outpostpmx/
    │
    ├── outpostx/
    ├── optermx/
    ├── HOWTO/
    ├── docs/
    ├── tools/
    │
    ├── README.md
    ├── LICENSE
    └── CHANGELOG.md
```

The repository should remain identical across all supported operating systems whenever practical.

---

# Chapter 4 - Python Virtual Environments

Each operating system maintains its own virtual environment.

Typical directory:

```text
outpostpmx/
│
└── venv/
```

The virtual environment isolates project dependencies from the operating system and allows each platform to maintain independent Python package versions.

---

# Chapter 5 - Required Python Packages

The following packages are currently required.

| Package     | Purpose               |
| ----------- | --------------------- |
| PySide6     | User interface        |
| PyInstaller | Application packaging |
| pyserial    | Serial communications |
| paramiko    | SSH communications    |

Additional packages may be introduced in future releases.

---

# Chapter 6 - Verifying the Environment

Before attempting a build, verify:

* Git is installed.
* Python executes correctly.
* Virtual environment activates successfully.
* Required packages are installed.
* Project source code is present.
* The repository reports a clean working tree.

Typical verification commands include:

```bash
git status
python --version
pip --version
pyinstaller --version
```

Platform-specific verification procedures are described in the platform build HOWTO documents.

---

# Design Decisions

**1. Decision:** Maintain independent virtual environments for each operating system.

**Reason:** Package versions and platform dependencies differ between Windows, Linux, and macOS.

**Alternative Considered:** Share one virtual environment across platforms.

**Reason Rejected:** Virtual environments are platform-specific and cannot be shared reliably.

---

## Summary

This HOWTO established the common development environment required to build and maintain the OutpostPMX Suite.

Platform-specific installation and build procedures are intentionally documented separately to minimize duplication and simplify future maintenance.

---

## Lessons Learned

Separating common development procedures from platform-specific installation details significantly reduces documentation maintenance.

When new Python packages are introduced, this document normally requires only a single update rather than modifications to every platform HOWTO.

---

## Checklist

Before proceeding to a platform-specific build HOWTO, verify:

* Development computer is operational.
* Git has been installed.
* Python has been installed.
* Virtual environment can be created.
* Required Python packages have been installed.
* OutpostPMX repository is available locally.
* Repository structure matches the documented layout.

---

## Notes

This HOWTO intentionally describes only the common development environment shared by all supported operating systems.

Platform-specific installation instructions are documented separately in:

* HOWTO_Build_Windows.md
* HOWTO_Build_Linux.md
* HOWTO_Build_macOS.md

---

## Looking Ahead

The development environment has now been established.

The next step is to follow the appropriate platform-specific HOWTO to build the OutpostPMX Suite for Windows, Linux, or macOS.
