# Chapter 2 - Daily Development Workflow

## Overview

The purpose of the daily development workflow is to provide a consistent process for developing, testing, and maintaining the OutpostPMX Suite.

Following the same workflow each development session helps ensure that source code, documentation, and project history remain synchronized. It also minimizes the risk of forgotten changes, accidental omissions, or inconsistent releases.

The workflow described in this chapter is intended for normal day-to-day development. Release-specific activities are covered in later chapters.

---

## Development Philosophy

Development should proceed in small, well-defined steps.

Whenever practical:

* Implement one logical feature or bug fix at a time.
* Test the change before beginning the next task.
* Update documentation when behavior changes.
* Commit related changes together.
* Keep the repository in a buildable state.

Small, incremental changes are easier to understand, test, review, and recover if problems occur.

---

## Typical Development Session

A normal development session follows the sequence below.

```text
Open Development Environment
        │
        ▼
Pull Latest Repository (if applicable)
        │
        ▼
Implement One Logical Change
        │
        ▼
Run Local Tests
        │
        ▼
Update Documentation
        │
        ▼
Review Modified Files
        │
        ▼
Commit Changes
        │
        ▼
Push to GitHub (optional)
```

Not every session requires pushing changes immediately. During active development, multiple local commits may be created before synchronizing with GitHub.

---

## Recommended Daily Procedure

1. Open the local OutpostPMX development directory.

2. Activate the appropriate Python virtual environment.

3. Verify the repository status.

```bash
git status
```

4. Confirm that the working tree is clean before beginning new work.

5. Implement the planned enhancement or bug fix.

6. Test the change.

Testing should be appropriate for the modification and may include:

* Running the application
* Exercising the modified feature
* Testing Windows, Linux, or macOS builds when appropriate
* Confirming that no existing functionality has been affected

7. Update project documentation whenever user-visible behavior changes.

Documentation should evolve with the software rather than becoming a separate task at release time.

8. Review modified files.

```bash
git status
```

This confirms exactly which files have changed before committing.

9. Continue development or proceed to Chapter 3 to commit the completed work.

---

## Documentation During Development

Documentation is considered part of the software.

Whenever practical, update documentation at the same time that code changes are made.

Examples include:

* HOWTO documents
* README files
* CHANGELOG entries
* Architecture documents
* User documentation
* Release notes

Keeping documentation current prevents large documentation efforts immediately before a software release.

---

## Good Development Practices

The following practices have proven effective during development of the OutpostPMX Suite.

* Develop one feature at a time.
* Test before committing.
* Avoid unrelated changes within the same commit.
* Keep commits focused on a single logical purpose.
* Record significant design decisions.
* Update documentation while the details are fresh.
* Leave the project in a buildable state whenever possible.

---

## Design Decisions

### Decision

Maintain a buildable project throughout development.

### Reason

A project that builds successfully at the end of each development session simplifies testing, troubleshooting, and future releases.

### Alternative Considered

Allow partially completed work to accumulate over multiple sessions.

### Reason Rejected

Long-lived incomplete changes make debugging more difficult and increase the likelihood of introducing unrelated regressions.

---

## Summary

This chapter described the recommended day-to-day workflow for developing the OutpostPMX Suite. By following a consistent development process, source code, documentation, and testing remain synchronized, reducing effort during future releases.

---

## Checklist

Before proceeding to Chapter 3, verify the following:

* Development task has been completed.
* Application builds successfully.
* Appropriate testing has been performed.
* Documentation has been updated if required.
* Repository status has been reviewed.
* Modified files are understood and expected.

---

## Notes

Experience has shown that frequent testing and small, well-defined changes are considerably easier to maintain than large batches of unrelated modifications.

A disciplined daily workflow significantly reduces the effort required to prepare public releases and simplifies long-term project maintenance.

---

## Looking Ahead

Once the current development task has been completed and verified, the next step is to permanently record the work by creating a Git commit. 
Chapter 3 describes how to prepare, review, and commit changes to the repository.