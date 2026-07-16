# HOWTO: Build OutpostPMX on macOS

**Document Version:** 1.0 \
**Last Updated:** 06-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 06-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This HOWTO describes the complete procedure for building the OutpostPMX Suite on macOS.

The reference build platform is an Intel (x86_64) Mac running macOS Sequoia. The objective is to produce a tested macOS distribution suitable for beta testing or public release.

---

# Document Scope

This document provides the macOS-specific build recipe.

Common build concepts are described in:

```text
HOWTO_10_Build_Overview.md
```

---

# Audience

Developers and maintainers responsible for producing macOS builds of the OutpostPMX Suite.

---

# Prerequisites

Before beginning:

* macOS development computer.
* Homebrew installed.
* Git installed.
* Python 3.12 or newer installed.
* OutpostPMX repository available.
* Internet connectivity (first-time setup).

---

# Document Conventions

This HOWTO follows the standards described in:

```text
HOWTO_00_Documentation_Style_Guide.md
```

---

# Chapter 1 - Prepare the Development Environment

Open Terminal.

Navigate to the development directory.

```bash
cd ~/dev
```

If this is a new system, clone the repository.

```bash
git clone https://github.com/Jimo706/outpostpmx.git
```

Enter the project directory.

```bash
cd outpostpmx
```

---

# Chapter 2 - Create the Python Virtual Environment

Create the virtual environment (if necessary).

```bash
python3.12 -m venv venv
```

Activate it.

```bash
source venv/bin/activate
```

Expected Result:

```text
(venv)
```

appears at the beginning of the Terminal prompt.

---

# Chapter 3 - Install Required Python Packages

Upgrade pip.

```bash
python -m pip install --upgrade pip
```

Install the required packages.

```bash
pip install pyside6
pip install pyinstaller
pip install pyserial
pip install paramiko
```

Verify installation.

```bash
python --version
pip --version
pyinstaller --version
```

Expected Result:

Current version information is displayed without errors.

---

# Chapter 4 - Verify the Repository

Confirm repository status.

```bash
git status
```

Expected Result:

```text
On branch main

nothing to commit, working tree clean
```

Verify the desired release tag.

```bash
git tag
```

---

# Chapter 5 - Build OutpostPMX

Run the macOS PyInstaller specification.

```bash
pyinstaller outpostpmx_macos.spec
```

Expected Result:

```text
dist/
    OutpostPMX/
    OutpostPMX.app/
```

Wait for PyInstaller to complete successfully before continuing.

---

# Chapter 6 - Verify the Build

Verify:

* OutpostX launches.
* OpTermX launches.
* Icons display correctly.
* Data directory is created.
* Configuration files are located correctly.
* Basic Send/Receive operation succeeds.

Whenever practical, perform a clean functional test before packaging.

---

# Chapter 7 - Create the Release Package

Create the release archive.

Example:

```bash
cd dist

zip -r ../release/outpostpmx-suite-macos-x86_64.zip OutpostPMX
```

Expected Result:

```text
release/

    outpostpmx-suite-macos-x86_64.zip
```

Verify:

* ZIP archive created.
* Archive extracts correctly.
* Applications launch from the extracted directory.

---

# Platform Notes

Current reference platform:

* macOS Sequoia (Intel x86_64)

Future work:

* Apple Silicon native builds
* Code signing
* Apple notarization

---

# Design Decisions

**1. Decision:** Build macOS releases on native macOS hardware.

**Reason:** Native builds provide the highest compatibility with macOS runtime requirements.

**Alternative Considered:** Cross-platform compilation.

**Reason Rejected:** Native builds simplify testing and reduce platform-specific issues.

---

## Summary

This HOWTO described the complete macOS build procedure for the OutpostPMX Suite.

Following these steps should produce a tested macOS distribution suitable for publication.

| Platform              | Status     | Notes                          |
| --------------------- | ---------- | ------------------------------ |
| macOS Intel (x86_64)  | ✅ Verified | Primary development platform   |
| Apple Silicon (ARM64) | ⏳ Planned  | Native build not yet completed |

---

## Lessons Learned

Building with the Homebrew version of Python eliminated several issues encountered when using the system-provided Python installation.

Using native macOS tools throughout the build process produced reliable and repeatable build results.

---

## Checklist

Before continuing to the GitHub release process, verify:

* Virtual environment activated.
* Required Python packages installed.
* Repository status verified.
* macOS build completed successfully.
* OutpostX verified.
* OpTermX verified.
* ZIP archive created.
* Archive contents verified.

---

## Notes

This HOWTO intentionally documents only the macOS-specific build procedure.

Common build concepts are maintained in HOWTO_10_Build_Overview.md.

As Apple Silicon development becomes available, this document should be updated to include the native ARM build procedure.

---

## Looking Ahead

The completed macOS package is now ready to be combined with the Windows and Linux packages.

The next step is to follow HOWTO_20_GitHub_Repository_and_Release_Process.md to prepare the software for public release.
