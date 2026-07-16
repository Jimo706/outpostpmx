# HOWTO: Documentation Style Guide

**Document Version:** 1.0 \
**Last Updated:** 06-Jul-2026

## Revision History

| Date        | Version | Description               |
| ----------- | ------- | ------------------------- |
| 06-Jul-2026 | 1.0     | Initial document created. |

---

# Purpose

This document establishes the documentation standards used throughout the OutpostPMX Project Maintenance Manual.

The objective is to create documentation that is consistent, easy to read, easy to maintain, and useful to both current and future project maintainers.

These standards apply to all HOWTO documents unless a specific document requires a different approach.

---

# Document Scope

This guide defines the preferred writing style, document organization, formatting conventions, and engineering philosophy used throughout the OutpostPMX HOWTO collection.

It does not define user documentation standards.

---

# Audience

This document is intended for anyone creating or maintaining technical documentation for the OutpostPMX Suite.

---

# Documentation Philosophy

The purpose of the OutpostPMX HOWTO collection is not simply to describe procedures.

Its purpose is to preserve the engineering knowledge, design decisions, and lessons learned that have shaped the OutpostPMX Suite.

Wherever practical, documentation should explain both:

* **How** a procedure is performed.
* **Why** the preferred approach was chosen.

Good documentation teaches the process as well as the procedure.

---

# General Writing Style

Documentation should be:

* Clear.
* Concise.
* Complete.
* Technically accurate.
* Easy to maintain.
* Written for future reference.

Assume the reader has not performed the procedure for many months.

Whenever practical, avoid unnecessary assumptions.

---

# Document Organization

Each HOWTO should follow this general structure.

```text
Title

Document Version
Last Updated
Revision History

Purpose
Document Scope
Audience
Prerequisites
Document Conventions

Chapter 1
...
Chapter N

Appendices (if applicable)
```

---

# Chapter Organization

Whenever practical, each chapter should follow this structure.

```text
Overview

(Body)

Design Decisions

Summary

Lessons Learned

Checklist

Notes

Looking Ahead
```

Not every chapter requires every section; however, consistency is encouraged whenever practical.

---

# Writing Principles

The following principles guide the OutpostPMX documentation.

## 1. Explain Why Before How

Begin by explaining the purpose of a procedure before describing the individual steps.

Understanding the objective makes the procedure easier to follow.

---

## 2. Procedures Are Recipes

A HOWTO should be executable without requiring the reader to continually switch between documents.

Operational commands should normally appear directly within the HOWTO.

Background information may be referenced from other documents.

---

## 3. Keep Documents Focused

Each HOWTO should have one primary responsibility.

Examples:

* Building Windows
* Building Linux
* GitHub Releases
* Development Environment

Avoid combining unrelated topics into a single document.

---

## 4. Record Engineering Decisions

Whenever an important engineering decision is made, document:

```text
Decision

Reason

Alternative Considered

Reason Rejected
```

Future maintainers should understand not only what was chosen, but why.

---

## 5. Capture Lessons Learned

Whenever a procedure reveals useful experience, record it.

Lessons Learned preserve practical knowledge that might otherwise be forgotten.

---

## 6. Write for Future You

Assume the reader has not performed the procedure in six months.

Provide sufficient commands, examples, and verification steps to complete the task without relying on memory.

---

## 7. Maintain a Single Source of Truth

Information that is shared across multiple HOWTO documents should have
one authoritative location.

Examples include:

* Version numbering
* Repository layout
* Engineering standards

Individual HOWTOs should reference these topics rather than duplicate
their explanations.

Operational commands and platform-specific procedures may be repeated
when doing so improves usability.

---

## 8 — A HOWTO should be self-contained.

A reader should be able to complete the procedure described in a HOWTO without continually referring to other HOWTOs.

Common background information may be referenced from other documents, but operational commands, verification steps, and platform-specific procedures should appear directly within the HOWTO whenever doing so improves readability and usability.

---

## 9. Verify, Don't Assume

Whenever practical, include verification steps.

A completed procedure should conclude with one or more methods that
confirm the expected result.

Examples include:

* git status
* pyinstaller --version
* Application launches successfully
* Repository reports a clean working tree

Verification builds confidence that the procedure completed
successfully.

---

## 10. Documentation Evolves With the Software

Documentation should be updated whenever software behavior,
engineering practices, repository organization, or build procedures
change.

Documentation is part of the project and should be maintained with the
same discipline as source code.

---

## 11. Knowledge Preservation

Documentation should preserve engineering knowledge,
not merely record commands.

---

# Formatting Standards

## Commands

Display commands in fenced code blocks.

Example:

```bash
git status
```

---

## File Names

Display file names using monospace formatting.

Example:

```text
README.md
```

---

## Directory Layouts

Use Unicode tree diagrams.

Example:

```text
outpostpmx/
│
├── HOWTO/
├── docs/
├── tools/
└── outpostx/
```

---

## Menu Selections

Display menu paths using arrows.

Example:

```text
File → Open
```

---

## Lists

Use bullet lists when sequence is unimportant.

Use numbered lists when order matters.

---

# Documentation Maintenance

Documentation should be updated whenever:

* Software behavior changes.
* Build procedures change.
* New tools are introduced.
* Lessons are learned.
* Repository organization changes.

Documentation should evolve with the software.

---

# Design Decisions

**1. Decision:** Standardize all OutpostPMX HOWTO documents.

**Reason:** Consistent documentation improves readability, simplifies maintenance, and creates a professional appearance.

**Alternative Considered:** Allow each document to develop independently.

**Reason Rejected:** Inconsistent documentation makes procedures more difficult to follow and maintain.

---

**2. Decision:** Treat HOWTO documents as engineering references rather than tutorials.

**Reason:** The primary audience is future project maintainers who require accurate, repeatable procedures.

**Alternative Considered:** Write informal instructional documents.

**Reason Rejected:** Tutorials often omit important engineering decisions and long-term maintenance considerations.

---

## Summary

This document establishes the documentation standards for the OutpostPMX Project Maintenance Manual.

Following these standards promotes consistency, preserves engineering knowledge, and simplifies long-term maintenance.

---

## Lessons Learned

Documentation should be treated with the same discipline as source code.

Well-written documentation reduces maintenance effort, shortens recovery time after long periods between releases, and captures valuable engineering knowledge that would otherwise be lost.

---

## Checklist

When creating or revising a HOWTO, verify:

* Purpose is clearly stated.
* Scope is appropriate.
* Chapters follow the standard organization.
* Design Decisions have been documented where appropriate.
* Lessons Learned have been recorded.
* Commands have been verified.
* Examples remain current.
* Looking Ahead points naturally to the next topic.

---

## Notes

Documentation is a living part of the OutpostPMX project.

Whenever the preferred engineering process changes, this document should be updated before revising other HOWTO documents.

This document serves as the foundation for all future project documentation.

---

## Closing Remarks

Good documentation is more than a collection of instructions.

It captures the experience, reasoning, and engineering practices that define a successful software project.

The objective of the OutpostPMX Project Maintenance Manual is to ensure that every important procedure, design decision, and lesson learned is preserved so that future development remains consistent, repeatable, and understandable.

As the OutpostPMX Suite evolves, this guide should evolve with it.
