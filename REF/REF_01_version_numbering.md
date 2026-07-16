# Appendix A - Version Numbering

## Overview

The OutpostPMX Suite uses a calendar-based version numbering system.

Calendar versioning provides an immediate indication of when a release was created while maintaining a simple and predictable release sequence.

Every public release of the OutpostPMX Suite is assigned a unique version number.

---

## Version Format

The standard version format is:

```text
YYYY.MM.R
```

where:

| Field | Description                     | Example |
| ----- | ------------------------------- | ------- |
| YYYY  | Four-digit year                 | 2026    |
| MM    | Two-digit month                 | 07      |
| R     | Release number within the month | 0       |

Example:

```text
2026.07.0
```

---

## Beta Releases

Beta releases append a beta identifier to the standard version.

Example:

```text
2026.07.0-beta1
2026.07.0-beta2
```

Multiple beta releases may be published before the final production release.

---

## Git Tags

Git tags always begin with the letter:

```text
v
```

Examples:

```text
v2026.07.0-beta1
v2026.07.0
v2026.08.0
```

The leading "v" is used only for Git tags.

Within the software itself, the version number normally appears without the leading "v".

Examples:

Application:

```text
2026.07.0
```

Git Tag:

```text
v2026.07.0
```

---

## Release Progression

A typical development cycle might appear as:

```text
2026.07.0-beta1
        │
        ▼
2026.07.0-beta2
        │
        ▼
2026.07.0
        │
        ▼
2026.08.0-beta1
        │
        ▼
2026.08.0
```

The exact number of beta releases depends upon testing results.

---

## Version Number Guidelines

The following guidelines are used when assigning version numbers.

* Increment the month when beginning a new planned release cycle.
* Increment the release number when multiple production releases occur within the same month.
* Use beta identifiers only for pre-release software.
* Never reuse a published version number.
* Never modify a published Git tag.

---

## Examples

| Version         | Description                             |
| --------------- | --------------------------------------- |
| 2026.07.0-beta1 | First public beta.                      |
| 2026.07.0-beta2 | Second beta with corrections.           |
| 2026.07.0       | Initial production release.             |
| 2026.07.1       | Maintenance release issued during July. |
| 2026.08.0       | New monthly release.                    |

---

## Design Decisions

**1. Decision:** Use calendar-based version numbers.

**Reason:** The version immediately indicates when the software was released while remaining simple to understand.

**Alternative Considered:** Semantic Versioning (Major.Minor.Patch).

**Reason Rejected:** Semantic versioning did not clearly communicate the release timeline and added complexity that was unnecessary for the OutpostPMX release process.

---

## Notes

Version numbers identify software releases.

Git tags identify the exact source code associated with those releases.

Although closely related, they serve different purposes and should not be considered interchangeable.

This appendix serves as the authoritative reference for all version numbering used throughout the OutpostPMX project.
