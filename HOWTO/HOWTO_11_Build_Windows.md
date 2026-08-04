# HOWTO: Build OutpostPMX on Windows

**Document Version:** 1.0 \
**Last Updated:** 06-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 06-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This HOWTO describes the complete procedure for building the OutpostPMX Suite on Microsoft Windows.

The objective is to produce a tested Windows distribution suitable for beta testing or public release.

---

# Document Scope

This document provides the Windows-specific build recipe.

Common build concepts are described in:

```text
HOWTO_10_Build_Overview.md
```

---

# Audience

Developers and maintainers responsible for producing Windows builds of the OutpostPMX Suite.

---

# Prerequisites

Before beginning:

* Windows development computer.
* Git installed.
* Python installed.
* OutpostPMX repository available.
* Internet connection (first-time setup).

---

# Document Conventions

This HOWTO follows the standards described in:

```text
HOWTO_00_Documentation_Style_Guide.md
```

---

# Chapter 1 - Prepare the Development Environment

Open a Windows Command Prompt.

Navigate to the development directory.

```cmd
cd C:\dev
```

If this is a new computer, clone the repository.

```cmd
git clone https://github.com/Jimo706/outpostpmx.git
```

Enter the project directory.

```cmd
cd outpostpmx
```

---

# Chapter 2 - Create the Python Virtual Environment

If the virtual environment does not already exist:

```cmd
python -m venv venv
```

Activate it.

```cmd
venv\Scripts\activate
```

The command prompt should now begin with:

```text
(venv)
```

---

# Chapter 3 - Install Required Python Packages

Install or update the required packages.

Example:

```cmd
pip install -U pip

pip install pyside6

pip install pyinstaller

pip install pyserial

pip install paramiko
```

Additional packages may be required as the project evolves.

Verify installed versions.

```cmd
python --version

pip --version

pyinstaller --version
```

---

# Chapter 4 - Verify the Repository

Confirm that the repository is clean.

```cmd
git status
```

Expected result:

```text
On branch main

nothing to commit, working tree clean
```

If preparing a release build, verify the intended release tag.

```cmd
git tag
```

---

# Chapter 5 - Build OutpostPMX

Run the Windows PyInstaller specification.

```cmd
pyinstaller outpostpmx_win.spec
```

The build process creates:

```text
dist\
│
└── outpostpmx\
    │
    ├── outpostx.exe
    ├── optermx.exe
    └── _internal\
```

Wait for PyInstaller to complete successfully before continuing.

---

# Chapter 6 - Verify the Build

Launch both applications.

Verify:

* OutpostX starts normally.
* OpTermX starts normally.
* Program icons display correctly.
* Version information is correct.
* Data directory is created.
* Sample Send/Receive session completes successfully.

If any verification step fails, correct the problem before packaging the release.

---

# Chapter 7 - Create the Release Package

Create the Windows release archive.

Example:

```cmd
7z a release\outpostpmx-windows-x86_64.zip dist\outpostpmx\
```

Verify:

* ZIP archive created successfully.
* Archive size appears reasonable.
* Archive extracts correctly.
* Applications execute from the extracted directory.

The completed archive is now ready for upload during the GitHub Release process.

---

# Design Decisions

**1. Decision:** Build the Windows release on a native Windows system.

**Reason:** Native builds provide the highest compatibility and simplify testing.

**Alternative Considered:** Cross-platform compilation.

**Reason Rejected:** Native builds have proven more reliable and easier to maintain.

---

## Summary

This HOWTO described the complete Windows build procedure for the OutpostPMX Suite.

Following these steps should produce a tested Windows release package suitable for publication.

---

## Lessons Learned

Building from a clean repository using an activated virtual environment eliminates many common build problems.

Verifying the applications before packaging is considerably faster than discovering problems after a release has been published.

---

## Checklist

Before continuing to the GitHub release process, verify:

* Virtual environment activated.
* Required Python packages installed.
* Repository status verified.
* Build completed successfully.
* OutpostX verified.
* OpTermX verified.
* Windows release archive created.
* Archive contents verified.

---

## Notes

This HOWTO intentionally documents only the Windows-specific build procedure.

Common build concepts are maintained in HOWTO_10_Build_Overview.md.

Whenever the Windows build process changes, update this HOWTO so it remains an accurate recipe.

---

## Looking Ahead

The completed Windows release package is now ready to be combined with the Linux and macOS packages.

The next step is to follow the corresponding platform HOWTO or proceed to HOWTO_20_GitHub_Repository_and_Release_Process.md to prepare the software for public release.
