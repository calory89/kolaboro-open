# Security policy

Kolaboro's security contact and policy are published at
**https://kolaboro.com/.well-known/security.txt** (RFC 9116). That file is the source of truth: if anything here disagrees with it, it wins.

At the time of writing it says: write to `hello@kolaboro.com`; we read every report and reply within two working days.
The full policy is at https://kolaboro.com/security.

## What is in scope here

- A verifier (`open/kolaboro-verify.js`, `open/kolaboro_verify.py`, `open/go/`) that accepts something it should reject:
  a forged signature, a log that was rewritten, a proof that does not lead to the published root.
- A verifier that rejects genuine data from kolaboro.com.
- The JavaScript, Python and Go verifiers disagreeing on any input.
- The scoring rules (`open/scoring.py`, `p/whatif.js`) breaking one of the invariants listed in the README.

Please do not include personal data of other people in a report, and do not test against kolaboro.com in ways that
degrade it for buyers (no load testing, no automated form submissions).

## Verifying a release

Release tarballs carry SLSA build provenance made by GitHub Actions. With the GitHub CLI:

    gh attestation verify kolaboro-open-<version>.tar.gz --repo <owner>/kolaboro-open

The command checks that the tarball was built by this repository's `release.yml` workflow from the tagged commit.
