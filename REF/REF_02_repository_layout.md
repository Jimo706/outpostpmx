# Appendix B - Repository Directory Layout

## Overview

The OutpostPMX GitHub repository is organized to separate application source code, documentation, build specifications, utilities, and release resources into well-defined directories.

The objective is to provide a consistent structure that supports long-term maintenance while keeping related files together.

This appendix describes the intended organization of the repository rather than an exhaustive listing of every file.

---

## Top-Level Repository

```text
outpostpmx/
│
├── outpostx/                  OutpostX application
├── optermx/                   OpTermX application
│
├── HOWTO/                     Project HOWTO documents
├── docs/                      Shared project documentation
├── tools/                     Development utilities
│
├── outpostpmx_win.spec        Windows suite build
├── outpostpmx_linux.spec      Linux suite build
├── outpostpmx_macos.spec      macOS suite build
│
├── README.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
│
├── polar3232.ico
├── polar3232.icns
└── polar3232.png
```

---

## OutpostX Directory

The `outpostx` directory contains the complete source code and resources for the OutpostX Packet Message Manager.

Typical contents include:

```text
outpostx/
│
├── config/
├── data/
├── dialogs/
├── docs/
├── services/
├── transports/
├── ui/
├── widgets/
│
├── outpostx.py
└── README.md
```

The internal organization of OutpostX is documented separately within the OutpostX project documentation.

---

## OpTermX Directory

The `optermx` directory contains the complete source code and resources for the OpTermX Packet Terminal.

Typical contents include:

```text
optermx/
│
├── config/
├── dialogs/
├── services/
├── transports/
├── views/
├── widgets/
│
├── optermx.py
└── README.md
```

As OpTermX evolves, additional directories may be added while preserving the overall organization.

---

## HOWTO Directory

The HOWTO directory contains project maintenance documentation.

Examples include:

```text
HOWTO/

    HOWTO_GitHub_Repository_and_Release_Process.md
    HOWTO_Build_Windows.md
    HOWTO_Build_Linux.md
    HOWTO_Build_macOS.md
    HOWTO_Setup_Development_Environment.md
```

Each HOWTO documents one specific maintenance activity.

---

## Documentation Directory

The `docs` directory contains documentation shared by the entire OutpostPMX Suite.

Examples include:

* Architecture documents
* Project planning
* User documentation
* Images
* Design notes

Documentation specific to an individual application should normally remain within that application's directory.

---

## Tools Directory

The `tools` directory contains development utilities that assist with building, packaging, testing, or maintaining the project.

Typical examples include:

* Build scripts
* Packaging scripts
* Archive creation scripts
* Utility programs

These tools support development but are not distributed as part of the software itself.

---

## Build Specification Files

The repository root contains the PyInstaller specification files used to create release packages.

Current build specifications include:

```text
outpostpmx_win.spec
outpostpmx_linux.spec
outpostpmx_macos.spec
```

These files define the platform-specific build configuration for the OutpostPMX Suite.

---

## Files Not Stored in Git

Several directories are intentionally excluded from version control.

Examples include:

```text
venv/
build/
dist/
__pycache__/
.pytest_cache/
.vscode/
.idea/
```

These directories contain generated files or development environment artifacts and are excluded through the `.gitignore` file.

---

## Repository Growth

The repository structure is expected to evolve as the project matures.

When adding new directories:

* Place related files together.
* Avoid unnecessary duplication.
* Keep directory names descriptive.
* Maintain consistency with the existing organization.
* Update this appendix when significant structural changes occur.

---

## Design Decisions

**1. Decision:** Maintain a single repository containing both OutpostX and OpTermX.

**Reason:** Both applications are developed, documented, tested, and released together as the OutpostPMX Suite.

**Alternative Considered:** Separate repositories for each application.

**Reason Rejected:** Separate repositories increase maintenance effort, duplicate documentation, and complicate synchronized releases.

---

## Notes

This appendix documents the intended repository organization rather than every individual file.

Minor additions and reorganizations are expected over time; however, the overall structure should remain stable to simplify maintenance, documentation, and future development.
