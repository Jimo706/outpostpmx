# HOWTO: Create the OutpostPMX Source Archive

**Document Version:** 1.0
**Last Updated:** 07-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 07-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This HOWTO describes the procedure for creating the portable OutpostPMX source archive.

The source archive provides a clean, self-contained copy of the OutpostPMX Suite that can be transferred to another development computer or archived for backup purposes.

This archive serves as the common starting point for Windows, Linux, and macOS builds.

---

# Document Scope

This document describes only the creation of the source archive.

It does **not** describe:

* Building executable files
* Creating release packages
* Publishing GitHub releases

Those topics are documented elsewhere within the Engineering Handbook.

---

# Audience

Developers and maintainers responsible for building or preserving the OutpostPMX Suite.

---

# Prerequisites

Before beginning:

* The OutpostPMX repository has been updated.
* Development and testing have been completed.
* The repository builds successfully.
* Unwanted temporary files have been removed.
* The repository reports a clean working tree.

---

# Document Conventions

This HOWTO follows the standards defined in:

```
HOWTO_00_Documentation_Style_Guide.md
```

---

# Chapter 1 – Verify the Repository

Before creating the archive:

* Confirm all desired changes have been committed.
* Verify the repository is current.
* Confirm the working tree is clean.

Example:

```bash
git status
```

Expected Result:

```
On branch main

nothing to commit, working tree clean
```

The source archive should always represent a known and reproducible state of the project.

---

# Chapter 2 – Verify the Project

Before archiving the source code:

* Verify OutpostX operates correctly.
* Verify OpTermX operates correctly.
* Verify recent documentation changes.
* Confirm version numbers are correct.
* Confirm release notes have been updated (if applicable).

The archive should never be created from an untested project.

---

# Chapter 3 – Create the Archive

The current implementation uses a Windows batch file.

Locate:

```
tools/
    create_outpostpmx_src_7zip.bat
```

Execute the script.

The script creates a compressed archive containing the OutpostPMX repository while excluding temporary build artifacts such as:

* venv
* build
* dist
* **pycache**
* .pytest_cache
* IDE-specific directories

These exclusions are consistent with the project's `.gitignore` policy.

---

# Chapter 4 – Verify the Archive

Expected output:

```
outpostpmx_archive.zip

outpostpmx_archive.log
```

Verify:

* Archive completed without errors.
* Archive log contains no unexpected warnings.
* Archive size appears reasonable.
* Archive contains the expected directory structure.

Typical contents include:

```
outpostpmx/

├── outpostx/
├── optermx/
├── HOWTO/
├── docs/
├── architecture/
├── tools/

├── README.md
├── CHANGELOG.md
├── LICENSE.md
└── .gitignore
```

The archive should not contain generated build directories.

---

# Chapter 5 – Test the Archive

As a final verification step:

1. Create a temporary test directory.
2. Extract the archive.
3. Verify the repository structure.
4. Confirm expected files are present.
5. Remove the temporary directory after verification.

Periodically testing the archive helps ensure that future builds begin from a known-good source package.

### Windows Extract commands

    cd C:\dev\test

    7z x outpostpmx-source-2026.07.0.zip  (unzip?)

**Expected Result**

    C:\dev\test\
        outpostpmx\
            outpostx\
            optermx\
            HOWTO\
            docs\
            tools\

### Linux Extract commands

    unzip x outpostpmx-source-2026.07.0.zip
    
**Expected Result**

    ~/dev/test/
        outpostpmx/
            outpostx/
            optermx/
            HOWTO/
            docs/
            tools/

### macOS Extract commands

    cd ~/dev/test

    unzip outpostpmx-source-2026.07.0.zip
    
**Expected Result**

    ~/dev/test/
        outpostpmx/
            outpostx/
            optermx/
            HOWTO/
            docs/
            tools/

### Verify

After extraction, verify:

* Repository directory structure is intact.
* All expected top-level directories are present.
* No build artifacts (such as venv, build, or dist) are included.
* Documentation files are present.
* The repository is ready for platform-specific builds.

---

# Design Decisions

**1. Decision:** Create a portable source archive before building release packages.

**Reason:** A portable archive provides a clean snapshot of the project that can be transferred to another development system or retained for long-term archival purposes.

**Alternative Considered:** Build directly from the active development directory.

**Reason Rejected:** Active development directories may contain temporary files, experimental changes, or platform-specific artifacts that should not become part of an archived release.

---

**2. Decision:** Exclude generated files from the source archive.

**Reason:** Build products, virtual environments, caches, and temporary files can always be regenerated from the source code.

**Alternative Considered:** Archive the complete development directory.

**Reason Rejected:** Including generated files significantly increases archive size while reducing portability and reproducibility.

---

## Summary

This HOWTO described the process used to create a portable OutpostPMX source archive.

The resulting archive represents a clean, verified snapshot of the project and serves as the common starting point for Windows, Linux, and macOS development environments.

---

## Lessons Learned

Creating a verified source archive before beginning platform-specific builds provides an additional layer of protection against data loss and ensures that every supported operating system begins from the same source code baseline.

The archive also serves as an excellent long-term historical record of each release.

---

## Checklist

Before continuing, verify:

* Repository status is clean.
* Applications have been tested.
* Version numbers are correct.
* Source archive created successfully.
* Archive log reviewed.
* Archive extracted successfully during a verification test.
* Repository structure verified.

---

## Notes

The current archive creation process uses a Windows batch file and 7-Zip.

Future implementations may replace this mechanism with a platform-independent Python utility while preserving the workflow described in this HOWTO.

---

## Looking Ahead

With a verified source archive available, the next step is to build the OutpostPMX Suite on the desired platform using:

* HOWTO_11_Build_Windows.md
* HOWTO_12_Build_Linux.md
* HOWTO_13_Build_macOS.md
