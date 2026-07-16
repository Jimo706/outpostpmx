# Chapter 3 - Committing Changes

## Overview

A Git commit permanently records a logical set of project changes in the local repository. Commits provide a historical record of software development and serve as milestones that can be reviewed, restored, or incorporated into future releases.

The objective of each commit is to capture one complete, tested, and well-defined enhancement or bug fix.

Commits should be created regularly during development rather than accumulating large numbers of unrelated changes.

---

## Commit Philosophy

Every commit should represent one logical unit of work.

Examples include:

* Implementing a new feature.
* Correcting a software defect.
* Updating documentation.
* Refactoring existing code.
* Revising build procedures.

Avoid combining unrelated work into a single commit whenever practical.

Smaller, focused commits simplify troubleshooting and make the project history easier to understand.

---

## Review the Repository

Before creating a commit, review the current repository status.

```bash
git status
```

Confirm that:

* Only the expected files have been modified.
* No temporary files have been added.
* No build artifacts are included.
* Documentation updates have been staged when appropriate.

---

## Stage the Changes

For most OutpostPMX development sessions, all completed work is staged together.

```bash
git add .
```

If necessary, individual files may also be staged separately.

Example:

```bash
git add outpostx/services/app_paths.py
```

After staging, verify the results.

```bash
git status
```

The files listed under **Changes to be committed** should represent one complete development task.

---

## Create the Commit

Create a descriptive commit message.

```bash
git commit -m "Implement configurable notification sounds"
```

The commit message should briefly describe the completed work.

Good examples include:

```text
Fix AGWPE connection timeout

Add Hot Key Profiles

Improve message editor layout

Update Linux build procedure

Correct station profile validation
```

Avoid vague commit messages such as:

```text
Updates

Changes

Misc fixes

More work
```

Future readers should be able to understand the purpose of the commit from the message alone.

---

## Verify the Commit

After the commit completes successfully, review the repository status.

```bash
git status
```

A successful commit normally reports:

```text
On branch main

nothing to commit, working tree clean
```

This confirms that all staged changes have been committed.

---

## When to Push

A commit records changes only in the local repository.

Uploading those commits to GitHub is a separate operation described in the next chapter.

During active development it is perfectly acceptable to make several local commits before pushing them to GitHub.

---

## Design Decisions

### Decision

Create frequent, focused commits throughout development.

### Reason

Smaller commits produce a more understandable project history and simplify troubleshooting.

### Alternative Considered

Create one large commit after completing several unrelated tasks.

### Reason Rejected

Large commits make it difficult to identify when a problem was introduced and complicate future maintenance.

---

## Summary

This chapter described how to prepare, review, stage, and commit changes to the local Git repository. Well-structured commits preserve the development history of the OutpostPMX Suite and provide a reliable foundation for future releases.

---

## Checklist

Before proceeding to Chapter 4, verify the following:

* Development work has been completed.
* Documentation has been updated if required.
* Repository status has been reviewed.
* All intended files have been staged.
* Commit message clearly describes the completed work.
* Repository reports a clean working tree after the commit.

---

## Notes

Commit early and commit often.

Frequent commits reduce risk, preserve development history, and provide convenient recovery points during future development.

A commit should represent a completed thought rather than a snapshot of work in progress.

---

## Looking Ahead

The completed commit now exists only within the local Git repository. The next step is to synchronize the local repository with GitHub and create an official project milestone by assigning a release tag. Chapter 4 describes how release tags identify important versions of the OutpostPMX Suite and prepare the project for future software releases.
