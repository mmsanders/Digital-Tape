# Product specification

**Canonical publication: Digital-Tape/main. Owner: PM.**
Exact revisions and SHA-256 values are in [VERSION.md](VERSION.md), enforced by
tools/ci/verify-spec-bundle.sh. Do not duplicate revision labels in onboarding headers.

The exact DRAFT-8 bundle has passed independent paper review and is published.
**Final Phase 0 sign-off is pending** in [the freeze record](../docs/PHASE0-FREEZE.md).
The hashed NOT FROZEN banners have deliberately not been edited.

| Surface | Gate |
|---|---|
| TapeFS §§1–8 | Phase 0 byte-level freeze |
| Engine API §§2–8 and §12 | Phase 0 candidate contract freeze |
| Acceptance criteria | Freeze with the format; not a declaration of passing tests |
| Operations and state matrix | First actual complete green WP-10 run |
| spec/hw/ | Hardware-owned, separately versioned; not part of this format freeze |

Code conforms to the spec. PM changes the contract first; independent tests follow;
implementation merges afterward. Software lands PM bytes mechanically and raises
suspected spec defects rather than editing them to fit code. Any change to a hashed
file requires a new authenticated bundle and applicable independent review.

The engine computes; the caller owns entropy, hardware knowledge and storage beyond
its budget. Identity/validity are written last. Ownership is not reference.
Detailed operation exceptions and physical assumptions remain in the normative text.

Historical references inside the authenticated bundle to absent Plan Rev B files
are retained to preserve reviewed bytes. The current [package index](../docs/PACKAGES/README.md)
and concrete WP files provide the repo-local operational mapping. See the freeze
record for the non-blocking V8R3-001 wording debt; do not silently repair hashed text.
