# Chapter 9 - Troubleshooting & Useful Git Commands

## Overview

This chapter summarizes the Git and GitHub commands most frequently used during development of the OutpostPMX Suite.

It also documents common problems encountered while maintaining the repository and their recommended solutions.

The objective is not to replace the Git documentation, but to provide a practical reference for routine project maintenance.

---

## Daily Git Commands

The following commands are used during normal development.

| Command                           | Purpose                          |
| --------------------------------- | -------------------------------- |
| `git status`                      | Display repository status.       |
| `git add .`                       | Stage all modified files.        |
| `git commit -m "message"`         | Create a local commit.           |
| `git push`                        | Upload commits to GitHub.        |
| `git pull`                        | Download changes from GitHub.    |
| `git tag`                         | Display existing tags.           |
| `git tag -a`                      | Create an annotated release tag. |
| `git push origin <tag>`           | Upload a release tag.            |
| `git log --oneline --decorate -5` | Display recent commit history.   |

---

## Useful Inspection Commands

These commands help verify repository state.

```bash
git status
```

Shows modified, staged, and untracked files.

```bash
git tag
```

Displays existing release tags.

```bash
git remote -v
```

Displays configured GitHub repositories.

```bash
git branch
```

Displays the current branch.

```bash
git log --oneline --decorate -10
```

Displays recent project history.

---

## Common Problems

**1. Problem:**  Repository reports:

```text
fatal: not a git repository
```

**Cause:**  Current directory is not inside a Git repository.

**Solution:**  Navigate to the project directory or initialize the repository.

---

**2. Problem:**  Push rejected because remote contains work not present locally.

**Cause:**  GitHub repository already contains commits.

**Solution:**  Commit local work before performing:

```bash
git pull origin main --allow-unrelated-histories
```

Resolve conflicts, then push.

---

**3. Problem:**  Nested Git repository detected.

**Cause:**  A project directory contains its own `.git` directory.

**Solution:**  Remove the nested `.git` directory and add the project folder to the parent repository.

---

**4. Problem:**  Unexpected files appear in `git status`.

**Cause:**  Missing or incorrect `.gitignore` entries.

**Solution:**  Review the `.gitignore` file and verify that generated files are excluded from version control.

---

**5. Problem:**  Release tag does not appear on GitHub.

**Cause:**  The tag was created locally but has not been pushed.

**Solution:**  

```bash
git push origin <tag>
```

---

## Recovery Tips

Before making significant changes:

* Verify repository status.
* Confirm the current branch.
* Review recent commits.
* Ensure the working tree is clean.

Frequent commits greatly simplify recovery from unexpected problems.

---

## Design Decisions

**1. Decision:** Maintain a concise Git reference specific to OutpostPMX.

**Reason:** Only a small subset of Git commands is required for routine project maintenance.

**Alternative Considered:** Document the complete Git command set.

**Reason Rejected:** Most Git functionality is unrelated to the OutpostPMX workflow and would unnecessarily complicate this HOWTO.

---

## Summary

This chapter collected the Git commands and troubleshooting techniques most frequently required when maintaining the OutpostPMX repository.

Rather than serving as a complete Git reference, it focuses on practical solutions to problems encountered during normal development and release activities.

---

## Lessons Learned

Many Git problems are easier to understand after running:

```bash
git status
```

This single command often provides enough information to identify the current state of the repository and determine the appropriate next step.

When in doubt, avoid guessing. Review the repository status first.

---

## Checklist

Periodically verify the following:

* Repository status is clean.
* Local repository is synchronized with GitHub.
* Release tags have been pushed.
* `.gitignore` excludes generated files.
* Recent commits accurately describe completed work.

---

## Notes

Git is an extremely powerful version control system.

Fortunately, maintaining the OutpostPMX Suite requires only a small subset of its capabilities. Consistently following the workflow described throughout this HOWTO is generally more valuable than memorizing additional Git commands.

This chapter should continue to evolve as new situations are encountered during future development.

---

## Looking Ahead

The appendices that follow summarize the version numbering convention, repository layout, and Git command reference used throughout the OutpostPMX project. These appendices are intended to provide a convenient quick-reference while using this HOWTO.

---

## Closing Remarks

The purpose of this document is not simply to describe Git commands. It is to establish a repeatable engineering process for maintaining the OutpostPMX Suite.

Following a consistent process helps ensure that every release is reproducible, every significant decision is documented, and every version of the software can be traced back to its source.

As the project evolves, this HOWTO should evolve with it. New lessons learned, improved procedures, and better practices should be incorporated so that the document continues to represent the preferred workflow for maintaining the OutpostPMX Suite.
