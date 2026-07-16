# HOWTO: Create the OutpostPMX Release Archive

**Document Version:** 1.0
**Last Updated:** 07-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 07-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This HOWTO describes the procedure for preparing the platform-specific release archives that will be distributed to end users.

The objective is to verify that every supported operating system has a tested, correctly named, and complete distributable package prior to publishing a GitHub Release.

---

# Document Scope

This document begins **after** the Windows, Linux, and macOS builds have been successfully completed.

It does not describe:

* Building the applications
* Creating the source archive
* Publishing the GitHub Release

---

# Audience

Developers and maintainers responsible for preparing an OutpostPMX software release.

---

# Prerequisites

Before beginning:

* Windows build completed successfully.
* Linux build completed successfully.
* macOS build completed successfully.
* Each platform has passed functional testing.
* Release version number has been finalized.

---

# Document Conventions

This HOWTO follows the standards defined in:

```text
HOWTO_00_Documentation_Style_Guide.md
```

---

# Chapter 1 – Collect the Release Packages

Verify that each platform package has been created.

Typical release directory:

```text
release/

    outpostpmx-windows-x86_64.zip

    outpostpmx-linux-x86_64.tar.gz

    outpostpmx-macos-x86_64.zip
```

Future releases may also include:

```text
outpostpmx-linux-arm64.tar.gz
outpostpmx-macos-arm64.zip
```

---

# Chapter 2 – Verify Package Names

Verify that each package follows the project naming convention.

Examples:

```text
outpostpmx-windows-x86_64.zip

outpostpmx-linux-x86_64.tar.gz

outpostpmx-macos-x86_64.zip
```

Each filename should clearly identify:

* Product
* Operating system
* Processor architecture

---

# Chapter 3 – Verify Package Contents

Extract each package into a temporary directory.

Verify that:

* Expected directory structure exists.
* Executable files are present.
* Icons are present.
* Configuration files are included.
* No unexpected temporary files are present.

Delete the temporary directory after verification.

---

# Chapter 4 – Verify Package Sizes

Confirm that package sizes appear reasonable.

Large unexpected changes in archive size may indicate missing files or accidental inclusion of build artifacts.

Typical archive sizes should remain relatively consistent between releases.

---

# Chapter 5 – Verify Platform Operation

For each platform:

* Extract the package.
* Launch OutpostX.
* Launch OpTermX.
* Verify application version.
* Verify application icons.
* Verify data directory creation.
* Perform a basic functional test.

Only verified packages should become release assets.

---

# Chapter 6 – Final Release Review

Before publishing:

Verify:

* Version numbers
* Git tag
* Release notes
* CHANGELOG
* Documentation updates
* Archive names
* Archive contents
* Archive sizes

The release should now be ready for publication.

---

# Design Decisions

**1. Decision:** Verify every release package before publication.

**Reason:** Discovering packaging problems before release is significantly easier than correcting published software.

**Alternative Considered:** Publish immediately after building.

**Reason Rejected:** Functional verification greatly reduces the likelihood of distributing incomplete or incorrect release packages.

---

**2. Decision:** Maintain consistent archive naming across all supported platforms.

**Reason:** Consistent naming simplifies downloads, documentation, and future automation.

**Alternative Considered:** Platform-specific naming conventions.

**Reason Rejected:** Multiple naming conventions increase confusion and complicate release management.

---

## Summary

This HOWTO described the preparation and verification of the OutpostPMX release packages.

The resulting archives represent the final software assets that will be uploaded during the GitHub Release process.

---

## Lessons Learned

The time required to verify release packages is small compared to the effort required to replace an incorrect public release.

A consistent verification process improves confidence in every published version.

---

## Checklist

Before continuing:

* Windows archive verified.
* Linux archive verified.
* macOS archive verified.
* Archive names verified.
* Archive contents verified.
* Archive sizes reviewed.
* Functional testing completed.
* Release notes completed.
* CHANGELOG updated.

---

## Notes

Release packages should be created only from successfully tested builds.

Whenever possible, preserve previous release packages to provide a historical archive of published software.

---

## Looking Ahead

The completed release packages are now ready to be uploaded.

Proceed to:

```text
HOWTO_20_GitHub_Repository_and_Release_Process.md
```

to create the GitHub Release and publish the OutpostPMX Suite.
