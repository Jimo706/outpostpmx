# Chapter 4 - Creating a Release Tag

## Overview

A Git release tag identifies a specific point in the development history of the OutpostPMX Suite.

Unlike a normal commit, which records incremental development work, a release tag marks an important milestone such as a public beta, production release, or maintenance update.

Release tags provide a permanent reference to the exact source code used to build a published version of the software.

---

## What Is a Release Tag?

A release tag is a permanent label attached to a specific Git commit.

For example:

```text
Commit A
Commit B
Commit C  ← v2026.07.0-beta1
Commit D
Commit E
```

The tag always points to the exact source used for that release, regardless of future development.

This allows any previous version of the software to be rebuilt or examined at a later date.

---

## Why Release Tags Matter

Release tags provide several important benefits.

They:

* Identify official software releases.
* Preserve the exact source used to build each release.
* Simplify future maintenance.
* Support reproducible builds.
* Provide meaningful milestones within the project history.

Without release tags it becomes much more difficult to determine exactly which source files produced a particular software release.

---

## Verify the Repository

Before creating a release tag, verify that the repository is ready.

```bash
git status
```

The repository should report:

```text
On branch main

nothing to commit, working tree clean
```

The software should also:

* Build successfully.
* Pass appropriate testing.
* Include all documentation updates.
* Contain the desired version number.

Only after these conditions have been satisfied should a release tag be created.

---

## Version Numbering

The OutpostPMX Suite uses calendar-based version numbers.

Examples:

```text
v2026.07.0-beta1
v2026.07.0
v2026.08.0
v2026.08.1
```

Version numbering conventions are described in Appendix A.

---

## Create the Tag

Create the release tag.

Example:

```bash
git tag v2026.07.0-beta1
git tag -a v2026.07.0-beta1 -m "OutpostPMX Suite 2026.07.0 Beta 1"
```

The first command creates the tag locally.\
The second command creates an annotated which are generally recommended for official releases.\
    The -a creates an annotated tag, and -m stores a description with it.


Verify the tag.

```bash
git tag
```

The newly created tag should appear in the list.

---

## Push the Tag to GitHub

Upload the tag.

```bash
git push origin v2026.07.0-beta1
```

After the push completes successfully, GitHub recognizes the new release tag.

The tag is now available when creating a GitHub Release.

---

## Verify on GitHub

Open the GitHub repository.

Select:

**Code → Releases → Draft a New Release**

The newly created tag should appear in the **Choose a Tag** list.

If the tag is not listed, verify that it has been pushed successfully.

---

## Design Decisions

### Decision

Use annotated calendar-based release tags.

### Reason

Calendar-based version numbers immediately identify when a release was created while maintaining a predictable versioning scheme.

Release tags permanently associate each published version with the exact source code used to build it.

### Alternative Considered

Sequential version numbers.

### Reason Rejected

Sequential numbering provides less information about the release timeline and requires maintaining a separate version history.

---

## Summary

This chapter described how release tags identify significant milestones within the OutpostPMX project.

A release tag permanently identifies the exact source code associated with a software release and prepares the repository for creation of a GitHub Release.

---

## Checklist

Before proceeding to Chapter 5, verify the following:

* Repository status is clean.
* Software builds successfully.
* Documentation has been updated.
* Version number has been verified.
* Release tag has been created.
* Release tag has been pushed to GitHub.
* Tag appears in the GitHub repository.

---

## Notes

A release tag should only be created after testing has been completed.

Once a release tag has been published and distributed, it should never be reused for a different version of the software.

If additional changes are required after a tag has been created, create a new commit and assign a new release tag rather than modifying an existing one.

---

## Looking Ahead

The source code has now been permanently identified by a release tag.

The next step is to build the release packages that will be distributed to users. Chapter 5 describes how the Windows, Linux, and macOS installation packages are created from the tagged source code.
