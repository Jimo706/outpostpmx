# HOWTO: Build OutpostPMX on Linux

**Document Version:** 1.0 \
**Last Updated:** 06-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 06-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This HOWTO describes the complete procedure for building the OutpostPMX Suite on Linux.

The reference build platform is Ubuntu 24.04 LTS. The same procedures have also been verified on Raspberry Pi OS (64-bit) with only minor platform differences.

The objective is to produce a tested Linux distribution suitable for beta testing or public release.

---

# Document Scope

This document provides the Linux-specific build recipe.

Common build concepts are described in:

```text
HOWTO_10_Build_Overview.md
```

---

# Audience

Developers and maintainers responsible for producing Linux builds of the OutpostPMX Suite.

---

# Prerequisites

Before beginning:

* Ubuntu 24.04 LTS or compatible Linux distribution.
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

Open a terminal.

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
python3 -m venv venv
```

Activate it.

```bash
source venv/bin/activate
```

Expected Result:

```text
(venv)
```

appears at the beginning of the shell prompt.

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

Confirm the repository status.

```bash
git status
```

Expected Result:

```text
On branch main

nothing to commit, working tree clean
```

For release builds, verify the desired Git tag.

```bash
git tag
```

---

# Chapter 5 - Build OutpostPMX

Run the Linux PyInstaller specification.

```bash
pyinstaller outpostpmx_linux.spec
```

Expected Result:

```text
dist/
└── outpostpmx/
    ├── outpostx
    ├── optermx
    └── _internal/
```

Wait for PyInstaller to complete successfully before continuing.

---

# Chapter 6 - Verify the Build

Verify both applications.

* Launch OutpostX.
* Launch OpTermX.
* Verify icons display correctly.
* Verify configuration directories are created.
* Verify a basic Send/Receive session.
* Verify OpTermX connects successfully.

Whenever practical, perform a clean functional test before packaging.

---

# Chapter 7 - Create the Release Package

Create the Linux distribution archive.

Example:

```bash
tar -czf release/outpostpmx-suite-linux-x86_64.tar.gz dist/outpostpmx
```

Expected Result:

```text
release/
└── outpostpmx-suite-linux-x86_64.tar.gz
```

Verify:

* Archive created successfully.
* Archive extracts correctly.
* Executables retain execute permissions.
* Applications launch after extraction.

---

# Platform Notes

Current reference platform:

* Ubuntu 24.04 LTS

Also verified:

* Raspberry Pi OS (64-bit)

Future Linux distributions may require additional package installation or configuration.

---

# Design Decisions

**1. Decision:** Use native Linux builds.

**Reason:** Native builds provide the best compatibility with Linux libraries and runtime behavior.

**Alternative Considered:** Building Linux executables from another operating system.

**Reason Rejected:** Native Linux builds have proven simpler, more reliable, and easier to troubleshoot.

---

## Summary

This HOWTO described the complete Linux build procedure for the OutpostPMX Suite.

Following these steps should produce a tested Linux distribution suitable for publication.

| Platform                   | Status           | Notes                        |
| -------------------------- | ---------------- | ---------------------------- |
| Ubuntu 24.04 LTS x86_64    | ✅ Verified       | Primary development platform |
| Raspberry Pi OS 64-bit ARM | ✅ Verified       | Native ARM build successful  |
| Debian                     | ⚪ Not yet tested | Expected to work             |
| Fedora                     | ⚪ Not yet tested | Not evaluated                |


---

## Lessons Learned

Maintaining the Linux build on a native Ubuntu system has resulted in reliable and repeatable builds.

Testing on Raspberry Pi OS demonstrated that the same source tree and build procedure can support both x86_64 and ARM64 platforms with only minor platform-specific adjustments.

---

## Checklist

Before continuing to the GitHub release process, verify:

* Virtual environment activated.
* Required Python packages installed.
* Repository status verified.
* Linux build completed successfully.
* OutpostX verified.
* OpTermX verified.
* Linux archive created.
* Archive contents verified.

---

## Notes

This HOWTO documents only the Linux-specific build procedure.

Common build concepts are maintained in HOWTO_10_Build_Overview.md.

As additional Linux distributions are verified, update the Platform Notes section accordingly.

---

## Looking Ahead

The completed Linux package is now ready to be combined with the Windows and macOS packages.

The next step is to follow HOWTO_13_Build_macOS.md or proceed to HOWTO_20_GitHub_Repository_and_Release_Process.md to prepare the software for public release.
