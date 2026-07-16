# Appendix C - Git Command Cheat Sheet

## Overview

This appendix provides a quick reference for the Git commands most commonly used while maintaining the OutpostPMX Suite.

It is intentionally limited to the commands required for the normal OutpostPMX development and release workflow.

---

## Check Repository Status

```bash
git status
```

Shows modified, staged, untracked, or conflicting files.

---

## Stage Changes

```bash
git add .
```

Stages all current changes.

Stage one file only:

```bash
git add path/to/file.py
```

---

## Commit Changes

```bash
git commit -m "Docs: Update GitHub release process"
```

Creates a local commit.

---

## Push Changes to GitHub

```bash
git push
```

Uploads committed local changes to GitHub.

First push from a new repository:

```bash
git push -u origin main
```

---

## Pull Changes from GitHub

```bash
git pull
```

Downloads and merges changes from GitHub.

When combining a new local repo with an existing GitHub repo:

```bash
git pull origin main --allow-unrelated-histories
```

---

## View Recent History

```bash
git log --oneline --decorate -5
```

Shows recent commits, tags, and branch locations.

---

## View Remote Repository

```bash
git remote -v
```

Shows the GitHub repository connected to the local repo.

---

## Create an Annotated Release Tag

```bash
git tag -a v2026.07.0-beta1 -m "OutpostPMX Suite 2026.07.0 Beta 1"
```

Creates an official release tag locally.

---

## Push a Release Tag

```bash
git push origin v2026.07.0-beta1
```

Uploads the release tag to GitHub.

---

## View Existing Tags

```bash
git tag
```

Lists all local tags.

---

## Fix a Staged File

Unstage one file:

```bash
git restore --staged path/to/file
```

Unstage everything:

```bash
git restore --staged .
```

---

## Keep Local Version During a Merge Conflict

```bash
git checkout --ours .gitignore
git add .gitignore
git commit -m "Resolve .gitignore merge conflict"
```

---

## Remove a File from Git Tracking Only

```bash
git rm --cached path/to/file
```

This removes the file from Git tracking but leaves it on disk.

---

## Remove a Nested Git Repository

If a subdirectory is accidentally treated as a separate Git repository:

```bash
git rm --cached outpostx
rmdir /s /q outpostx\.git
git add outpostx/
```

Use caution. Do not remove the top-level `.git` directory.

---

## Normal Daily Workflow

```bash
git status
git add .
git commit -m "Describe the completed work"
git push
```

---

## Normal Release Tag Workflow

```bash
git status
git tag -a v2026.07.0-beta1 -m "OutpostPMX Suite 2026.07.0 Beta 1"
git push origin v2026.07.0-beta1
```

---

## Notes

Most OutpostPMX maintenance requires only a small number of Git commands.

When unsure what to do next, run:

```bash
git status
```

This command usually provides the safest starting point.
