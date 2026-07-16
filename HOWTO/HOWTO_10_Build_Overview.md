# HOWTO: Build Overview

**Document Version:** 1.0 \
**Last Updated:** 06-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 06-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This document describes the common procedures used to build the OutpostPMX Suite.

The objective is to establish a consistent, repeatable build process that applies to all supported operating systems.

Platform-specific installation and build commands are documented separately in the Windows, Linux, and macOS build HOWTO documents.

---

# Document Scope

This HOWTO describes the build process common to every supported platform.

Topics include:

* Build philosophy
* Repository organization
* Development environment
* Python virtual environments
* Required Python packages
* Build verification
* Release packaging

Platform-specific installation commands are intentionally documented elsewhere.

---

# Audience

This document is intended for developers and maintainers responsible for building or maintaining the OutpostPMX Suite.

---

# Prerequisites

Before beginning:

* Administrative access to the development computer.
* Internet connectivity.
* Access to the OutpostPMX GitHub repository.
* Basic familiarity with command-line operation.

---

# Document Conventions

This HOWTO follows the standards defined in:

```text id="w8z0j8"
HOWTO_Documentation_Style_Guide.md
```

---

# Chapter 1 - Build Philosophy

The OutpostPMX Suite is developed using native build environments.

Current supported build platforms are:

| Platform | Build Environment |
| -------- | ----------------- |
| Windows  | Windows 11        |
| Linux    | Ubuntu Linux      |
| macOS    | macOS             |

Each operating system maintains its own Python virtual environment while sharing the same repository structure and release workflow.

The objective is that every supported platform produces functionally equivalent software packages from the same source code.

---

# Chapter 2 - Repository Organization

The recommended repository layout is:

```text id="q9q5ho"
dev/
│
└── outpostpmx/
    │
    ├── outpostx/
    ├── optermx/
    ├── HOWTO/
    ├── docs/
    ├── architecture/
    ├── tools/
    │
    ├── README.md
    ├── CHANGELOG.md
    └── LICENSE
```

All supported platforms should use the same repository organization whenever practical.

---

# Chapter 3 - Development Environment

Every supported platform should provide:

* Git
* Python
* Python virtual environment (venv)
* pip
* PySide6
* PyInstaller
* pyserial
* paramiko

Platform-specific installation procedures are described in the corresponding platform HOWTO.

---

# Chapter 4 - Python Virtual Environments

Each operating system maintains its own independent virtual environment.

Typical layout:

```text id="6s3mt5"
outpostpmx/
│
└── venv/
```

Using a virtual environment isolates project dependencies from the operating system and allows each platform to maintain independent package versions.

---

# Chapter 5 - Preparing for a Build

Before beginning any build:

* Verify the repository is current.
* Verify the working tree is clean.
* Activate the virtual environment.
* Confirm required Python packages are installed.
* Verify the application version number.
* Verify the desired Git tag (for release builds).

Typical verification includes:

```bash id="xglb57"
git status
python --version
pip --version
pyinstaller --version
```

---

# Chapter 6 - Platform-Specific Builds

Platform-specific build procedures are documented separately.

| Platform | HOWTO                  |
| -------- | ---------------------- |
| Windows  | HOWTO_Build_Windows.md |
| Linux    | HOWTO_Build_Linux.md   |
| macOS    | HOWTO_Build_macOS.md   |

Each document describes:

* Development environment preparation
* Platform-specific commands
* Build procedures
* Packaging
* Platform verification
* Known platform considerations

---

# Chapter 7 - Build Verification

Regardless of operating system, every completed build should verify:

* Application starts successfully.
* Application icon displays correctly.
* Configuration files are located correctly.
* Data directory is created correctly.
* Primary application functions operate normally.
* Release package contains the expected files.

Verification should be performed before distributing the software.

---

# Chapter 8 - Release Packaging

After a successful build:

* Create the platform release package.
* Verify package contents.
* Verify package naming.
* Move the package into the release directory.
* Repeat for each supported platform.

The completed release packages become the assets uploaded during the GitHub Release process.

---

# Design Decisions

**1. Decision:** Build each operating system using its native development environment.

**Reason:** Native builds provide the highest level of compatibility and simplify testing.

**Alternative Considered:** Cross-platform compilation.

**Reason Rejected:** Native builds have proven more reliable and easier to maintain.

---

**2. Decision:** Maintain identical repository organization across all platforms.

**Reason:** Consistent directory structures simplify documentation, troubleshooting, and long-term maintenance.

**Alternative Considered:** Platform-specific repository layouts.

**Reason Rejected:** Multiple repository layouts increase documentation complexity and developer confusion.

---

## Summary

This HOWTO described the common build philosophy and workflow shared by all supported OutpostPMX development platforms.

Platform-specific details are intentionally separated into dedicated HOWTO documents, allowing this document to remain stable as operating systems and development tools evolve.

---

## Lessons Learned

Although each operating system requires different installation commands, the overall build process remains remarkably consistent.

Separating common build concepts from platform-specific implementation greatly reduces documentation maintenance while preserving complete build procedures within each platform HOWTO.

---

## Checklist

Before proceeding to a platform-specific build HOWTO, verify:

* Repository has been cloned successfully.
* Repository layout matches the documented structure.
* Development environment has been prepared.
* Python virtual environment has been created.
* Required Python packages have been installed.
* Repository status has been verified.
* Target version has been identified.

---

## Notes

This HOWTO intentionally avoids platform-specific commands.

Those commands remain within the Windows, Linux, and macOS build HOWTO documents so that each build procedure can be followed independently as a complete recipe.

---

## Looking Ahead

With the common build process understood, the next step is to follow the appropriate platform-specific HOWTO:

* HOWTO_Build_Windows.md
* HOWTO_Build_Linux.md
* HOWTO_Build_macOS.md

Each document provides the complete build recipe for its respective operating system.
