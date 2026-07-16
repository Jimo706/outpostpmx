# Chapter 5 - Building the Release Packages

## Overview

Once a release tag has been created, the next step is to build the software packages that will be distributed to users.

The OutpostPMX Suite currently supports three operating systems:

* Windows
* Linux
* macOS

Each platform is built using its own native development environment and platform-specific build specification.

The objective of this chapter is to produce tested release packages that correspond exactly to the tagged source code.

---

## Build Philosophy

Each operating system should be built on its native platform whenever practical.

Current development environments are:

| Platform | Build Environment |
| -------- | ----------------- |
| Windows  | Windows 11        |
| Linux    | Ubuntu Linux      |
| macOS    | macOS             |

Although cross-compilation tools exist, native builds generally provide the most reliable and repeatable results.

---

## Verify the Source

Before beginning any build, verify:

* Repository is clean.
* Release tag has been created.
* Correct branch is checked out.
* Documentation is current.
* Software has passed testing.

```bash
git status
```

A clean repository ensures the release package accurately represents the tagged source code.

---

## Platform Build Procedures

Detailed build instructions are maintained in separate HOWTO documents.

| Platform | HOWTO                  |
| -------- | ---------------------- |
| Windows  | HOWTO_Build_Windows.md |
| Linux    | HOWTO_Build_Linux.md   |
| macOS    | HOWTO_Build_macOS.md   |

Those documents describe:

* Python environment
* Required packages
* Build commands
* PyInstaller specifications
* Packaging procedures
* Platform-specific considerations

This document assumes those procedures have already been completed successfully.

---

## Expected Release Artifacts

The current release produces installation packages similar to:

```text
outpostpmx-windows-x86_64.zip
outpostpmx-linux-x86_64.tar.gz
outpostpmx-macos-x86_64.zip
```

Additional packages may be added in the future, including:

```text
outpostpmx-linux-arm64.tar.gz
```

for Raspberry Pi and other ARM platforms.

---

## Verify Each Package

Before publishing a release, each package should be tested on its intended platform.

Verification should include:

* Application launches successfully.
* Icons display correctly.
* Configuration files are located properly.
* Data directories are created correctly.
* Basic program functionality operates normally.
* Packaging contains expected files.
* No unexpected build artifacts are present.

Whenever practical, perform a clean installation on a test system.

---

## Organize Release Files

Once verified, collect all release packages into a common release directory.

Example:

```text
release/

    outpostpmx-windows-x86_64.zip
    outpostpmx-linux-x86_64.tar.gz
    outpostpmx-macos-x86_64.zip
```

These packages will later be uploaded to the GitHub Release.

---

## Design Decisions

### Decision

Build each supported operating system using its native platform.

### Reason

Native builds produce the most reliable executables, simplify testing, and reduce platform-specific issues.

### Alternative Considered

Cross-compiling all releases from a single operating system.

### Reason Rejected

Cross-platform build environments frequently introduce additional complexity and may not accurately reproduce the behavior of native builds.

---

## Summary

This chapter described the process used to build and verify the release packages for the OutpostPMX Suite.

The objective is to produce tested installation packages that correspond exactly to the tagged source code and are ready for publication.

---

## Checklist

Before proceeding to Chapter 6, verify the following:

* Repository was clean before building.
* Release tag matches the intended version.
* Windows package built successfully.
* Linux package built successfully.
* macOS package built successfully.
* All packages have been tested.
* Release files have been collected into the release directory.

---

## Notes

Platform-specific build procedures evolve over time as Python, PyInstaller, and operating systems change.

Rather than duplicating those details here, maintain the platform-specific build procedures in their respective HOWTO documents.

This document should describe the release workflow, while the individual build HOWTOs describe how each package is produced.

---

## Looking Ahead

The software packages have now been built and verified.

The next step is to create a Draft Release on GitHub, upload the completed installation packages, and prepare the release notes prior to publication. Chapter 6 describes that process.
