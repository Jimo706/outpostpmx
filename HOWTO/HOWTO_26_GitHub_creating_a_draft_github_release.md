# Chapter 6 - Creating a Draft GitHub Release

## Overview

Once the release packages have been built and verified, the next step is to prepare a Draft Release on GitHub.

A Draft Release provides a private workspace where the release can be assembled, reviewed, and refined before it becomes publicly available.

The draft release associates the previously created Git tag with release notes and downloadable installation packages.

---

## Draft Release Philosophy

Creating a Draft Release allows the project maintainer to verify every aspect of the release before making it public.

While a release remains in Draft status:

* It is not visible to the public.
* Release notes may be edited.
* Installation packages may be added or replaced.
* Release titles may be modified.
* Files may be reviewed before publication.

This provides an opportunity to perform a final quality review before announcing the release.

---

## Prerequisites

Before creating a Draft Release, verify that:

* The release tag has been created.
* The release tag has been pushed to GitHub.
* All platform packages have been successfully built.
* Installation packages have been tested.
* Release notes have been prepared.

---

## Open the GitHub Repository

Using a web browser, open the OutpostPMX GitHub repository.

Navigate to:

```text
Releases
```

Select:

```text
Draft a new release
```

---

## Select the Release Tag

Choose the Git tag created in Chapter 4.

Example:

```text
v2026.07.0-beta1
```

The selected tag identifies the exact source code associated with this release.

---

## Enter the Release Title

The release title should clearly identify the software version.

Example:

```text
OutpostPMX 2026.07.0 Beta 1
```

Maintain a consistent naming convention across all releases.

---

## Enter the Release Notes

Release notes summarize the changes included in the release.

Typical sections include:

* Overview
* New Features
* Bug Fixes
* Known Issues
* Platform Notes
* Installation Notes

Release notes should be written for users rather than developers.

Whenever practical, describe the benefits of each change rather than the implementation details.

---

## Upload the Release Packages

Attach the completed installation packages.

Typical release assets include:

```text
outpostpmx-windows-x86_64.zip
outpostpmx-linux-x86_64.tar.gz
outpostpmx-macos-x86_64.zip
```

GitHub also automatically provides downloadable source archives for the tagged version.

---

## Save the Draft

Rather than publishing immediately, select:

```text
Save draft
```

The draft release can be reopened and edited at any time.

Saving the draft allows additional review before making the release publicly available.

---

## Review the Draft

Before publishing, review:

* Release title
* Version number
* Release notes
* Uploaded assets
* Platform names
* File names
* Installation instructions
* Links
* Formatting

This review serves as the final quality check prior to publication.

---

## Design Decisions

### Decision

Create every GitHub Release as a Draft before publication.

### Reason

A Draft Release provides an opportunity to review the release package in its entirety before it becomes visible to users.

It also allows additional installers, documentation, or release notes to be added without exposing an incomplete release.

### Alternative Considered

Publish immediately after uploading assets.

### Reason Rejected

Immediate publication increases the likelihood of incomplete documentation, missing installation packages, or typographical errors.

---

## Summary

This chapter described how to create a Draft GitHub Release using the previously created Git tag and completed installation packages.

A Draft Release provides a safe environment to review the release before making it publicly available.

---

## Lessons Learned

**Lessons Learned (July 2026)**: It is perfectly acceptable—and recommended—to leave a release in Draft status while additional installers, documentation, or testing are being completed. A Draft Release is private and serves as a staging area prior to publication.

---

## Checklist

Before proceeding to Chapter 7, verify the following:

* Correct release tag selected.
* Release title entered.
* Release notes completed.
* Windows package uploaded.
* Linux package uploaded.
* macOS package uploaded (if available).
* Source archives verified.
* Draft Release saved.
* Final review completed.

---

## Notes

Creating a Draft Release does not make the software publicly available.

The Draft Release should be considered a staging area where the complete release can be assembled and verified before publication.

Taking a few extra minutes to review the draft often prevents errors that would otherwise become part of the permanent public release history.

---

## Looking Ahead

The release has now been fully assembled and reviewed.

The final step is to publish the GitHub Release, making it publicly available for download. Chapter 7 describes the publication process and the activities that typically follow the release announcement.
