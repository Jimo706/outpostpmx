# Chapter 7 - Publishing the Release

## Overview

Once the Draft Release has been reviewed and verified, the final step is to publish it on GitHub.

Publishing a release makes the release page and its associated installation packages publicly available. The release becomes part of the permanent release history of the OutpostPMX Suite.

Only publish a release after all testing, documentation, and package verification have been completed.

A release is more than a collection of files—it is a commitment to support a specific version of the software.

---

## Publication Philosophy

Publishing a release represents a commitment that the software is ready for public use within the stated release objectives.

For beta releases, this means the software is considered suitable for evaluation and testing by the Amateur Radio community.

For production releases, it indicates that the software is considered ready for general use.

Every published release becomes part of the permanent project history.

---

## Final Review

Before selecting **Publish release**, perform one final review of the Draft Release.

Verify:

* Release tag is correct.
* Release title is correct.
* Version number matches the software.
* Release notes are complete.
* Installation packages are present.
* Platform names are correct.
* Documentation links are valid.
* Downloaded packages have been tested.

If any corrections are required, return to the Draft Release and make the necessary updates before publishing.

---

## Publish the Release

From the Draft Release page, select:

```text id="tfj5wc"
Publish release
```

GitHub immediately:

* Makes the release page publicly visible.
* Publishes the attached installation packages.
* Associates the release with the selected Git tag.
* Adds the release to the project's Release History.
* Makes the release available for download.

Publishing the release does not modify the source code repository.

---

## Verify the Published Release

After publication, open the newly published release page.

Verify:

* Release title displays correctly.
* Release notes are formatted properly.
* All release assets are present.
* Source archives are available.
* Download links function correctly.

Whenever practical, download one of the published installation packages directly from GitHub to confirm that the uploaded file is correct.

---

## Announce the Release

Once the published release has been verified, notify intended users through the appropriate communication channels.

Examples include:

* Project web site.
* Amateur Radio mailing lists.
* User groups.
* Beta test mailing list.
* Social media.
* Club newsletters.

Announcements should include:

* Release version.
* Summary of major changes.
* Download location.
* Known limitations.
* Request for feedback.

---

## Design Decisions

### Decision

Always publish only after a successful Draft Release review.

### Reason

The Draft Release process significantly reduces the likelihood of publishing incomplete documentation, missing files, or incorrect release information.

### Alternative Considered

Publishing immediately after uploading release assets.

### Reason Rejected

Immediate publication provides little opportunity to perform a comprehensive quality review and increases the likelihood of avoidable errors.

---

## Summary

Publishing a GitHub Release makes the software available to users and establishes an official milestone in the history of the OutpostPMX Suite.

Once published, the release becomes the reference point for user support, bug reports, and future maintenance updates.

---

## Lessons Learned

A published release is permanent project history.

Although GitHub allows a published release to be edited, the preferred practice is to complete all testing, documentation, and verification while the release remains in Draft status.

Careful preparation before publication results in a more professional release and reduces the need for post-publication corrections.

---

## Checklist

Before proceeding to Chapter 8, verify the following:

* Draft Release has been thoroughly reviewed.
* Release has been published.
* Published release page has been verified.
* Installation packages download correctly.
* Release notes display correctly.
* Source archives are available.
* Release announcement has been prepared or distributed.

---

## Notes

Publishing the release marks the transition from software development to software support.

Following publication, users may begin reporting installation issues, software defects, enhancement requests, or documentation improvements. These become the starting point for planning the next development cycle.

---

## Looking Ahead

The release is now publicly available.

The next chapter describes the activities that typically occur after publication, including monitoring user feedback, tracking reported issues, planning maintenance releases, and preparing for the next development cycle.
