# HOWTO: GitHub Repository and Release Process

**Document Version:** 1.0
**Last Updated:** 06-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 06-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This document describes the standard GitHub workflow used to develop, maintain, package, and publish the **OutpostPMX Suite**.

It is written as a practical, step-by-step cookbook rather than a comprehensive Git or GitHub reference. The objective is to provide a repeatable process that can be followed regardless of how much time has elapsed since the previous software release.

The procedures described here have been developed and tested during the ongoing development of OutpostPMX and reflect the project's preferred workflow. As the project evolves, this document should be updated so it continues to represent the current release process.

Following these procedures helps ensure that every public release is built, packaged, documented, and published in a consistent manner.

The objective of the OutpostPMX HOWTO collection is not merely to describe procedures, but to preserve the knowledge, engineering decisions, and lessons learned during the development and maintenance of the OutpostPMX Suite. Wherever practical, the documentation explains both how a task is performed and why the preferred approach was chosen.

---

# Document Scope

This document describes the GitHub workflow used to maintain the
OutpostPMX Suite repository and publish official software releases.

It does not describe:

* Python programming
* Application architecture
* Operating system installation
* PyInstaller configuration
* Platform-specific build procedures

Those topics are documented in separate HOWTO documents.

---

# Audience

This document is intended for anyone responsible for maintaining,
building, or publishing the OutpostPMX Suite.

The primary audience is the project maintainer; however, future
contributors and release managers should also be able to follow the
procedures described here.

It assumes responsibility for:

* Maintaining the GitHub repository.
* Managing source code revisions.
* Building release packages for Windows, Linux, and macOS.
* Publishing GitHub Releases.
* Maintaining project documentation.
* Responding to bug reports and preparing future releases.

Although written for the primary maintainer, future project contributors may also find this document useful when assisting with development or preparing software releases.

---

# Document Conventions

Throughout this document:

* Commands entered at a command prompt appear in a monospace font.
* File and directory names are shown in monospace.

* Menu selections are written as:

    File → Open

* Repository and directory layouts are illustrated using Unicode tree diagrams.

    Example:

        outpostpmx/
        │
        ├── outpostx/
        ├── optermx/
        ├── HOWTO/
        └── tools/

* Notes identify helpful information.
* Warnings identify operations that could result in data loss or unintended changes.

---

# Prerequisites

Before using this document, the following should already be in place:

## Development Environment

* Git is installed and configured.
* A GitHub account has been created.
* The OutpostPMX GitHub repository exists.
* The local development repository has been cloned or initialized.
* Python virtual environments have been created for each supported platform.
* The required Python packages have been installed.

## Repository Organization

The OutpostPMX repository contains both primary applications:

* OutpostX
* OpTermX

along with shared documentation, build specifications, utilities, and release support files.

## Platform Build Capability

The maintainer should be able to successfully build release packages for the intended platforms:

* Windows
* Linux
* macOS

Build procedures for each operating system are documented separately within the OutpostPMX HOWTO collection.

## Familiarity

Readers are expected to have a basic understanding of:

* Windows, Linux, and macOS file systems.
* Command-line operation.
* Basic Git commands.
* GitHub navigation.

No prior knowledge of advanced Git features such as branching strategies, rebasing, or pull requests is required for the workflow described in this document.
