# Chapter 1 - Repository Organization

## Overview

The OutpostPMX GitHub repository is the master source for all software, documentation, build specifications, and release support files associated with the OutpostPMX Suite.

The repository is organized to separate the two primary applications while keeping all shared project resources in a single location. This structure simplifies development, allows both applications to share common documentation and release procedures, and provides a single location for source code backups and version control.

All changes to the project should originate from this repository. The GitHub repository should always represent the current state of development.

---

## Repository Philosophy

The OutpostPMX Suite consists of two independent applications that are developed and released together.

* **OutpostX** – Packet Message Manager
* **OpTermX** – Packet Terminal

Although each application can be developed independently, they are maintained within a single repository because they share:

* Release schedules
* Documentation
* Build procedures
* Project history
* Version numbering
* Installation media

Maintaining both applications in one repository simplifies project maintenance and ensures that a release of the OutpostPMX Suite always represents a known, tested combination of both applications.

---

## Repository Layout

The top-level repository currently follows this general organization.

```text
outpostpmx/
│
├── outpostx/                  Primary OutpostX application
├── optermx/                   Primary OpTermX application
│
├── HOWTO/                     Project HOWTO documents
├── docs/                      Shared project documentation
├── tools/                     Build and utility scripts
│
├── outpostpmx_win.spec
├── outpostpmx_linux.spec
├── outpostpmx_macos.spec
│
├── LICENSE
├── README.md
├── CHANGELOG.md
├── .gitignore
│
├── polar3232.ico
├── polar3232.icns
└── polar3232.png
```

As the project evolves, additional directories may be added. However, the overall organization should remain stable to minimize disruption for developers and contributors.

---

## Files Not Maintained in Git

The repository intentionally excludes generated files and temporary development artifacts.

Examples include:

* Python virtual environments (`venv`)
* Build directories (`build`)
* Distribution packages (`dist`)
* Python cache directories (`__pycache__`)
* Temporary editor files
* Platform-specific temporary files

These files are regenerated as needed and should never be committed to the repository.

The `.gitignore` file defines which files and directories Git excludes from version control.

---

## Repository Principles

The following principles guide maintenance of the OutpostPMX repository.

1. Source code is always maintained under version control.

2. Generated files are never committed unless specifically required for a release.

3. Documentation is maintained alongside the source code whenever practical.

4. Build specifications are version controlled.

5. Repository organization should favor long-term maintainability over short-term convenience.

6. Every public release must be reproducible from the contents of the repository.


---

## Design Decisions

**Decision:**
Maintain OutpostX and OpTermX in a single repository.

**Reason:**
Both applications are released together and share documentation,
build procedures, and version numbering.

**Alternative Considered:**
Separate repositories for each application.

**Reason Rejected:**
Would require duplicate documentation, separate release processes,
and additional synchronization between projects.


---

## Summary

This chapter introduced the organization of the OutpostPMX repository and explained why the project is maintained as a single GitHub repository containing both OutpostX and OpTermX. It also identified the types of files that belong under version control and those that should remain local development artifacts.

---

## Checklist

Before continuing to Chapter 2, verify the following:

* Repository has been created on GitHub.
* Local repository is connected to the GitHub repository.
* Repository contains both OutpostX and OpTermX.
* `.gitignore` is functioning correctly.
* Build and virtual environment directories are excluded from Git.
* Repository layout matches the documented structure.

---

## Notes

The repository organization described in this chapter represents the project's preferred long-term structure.

Future enhancements should preserve this organization whenever practical. Stable directory layouts simplify maintenance, reduce documentation updates, and make the project easier for future contributors to understand.
