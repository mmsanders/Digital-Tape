# spec/hw — version manifest

**Owner:** Hardware Lead · **Checked by:** `make -C hardware spec-check`, and in CI

Taking up the pattern PM Decisions 005 §5 offers. The PM found `main` publishing three
spec files at three revisions, each claiming in its header to be versioned in step —
the third silent desync on this project, all three caught by a person happening to look
and none by a mechanism.

**Here it protects something specific.** `board-rev-a.md` is the contract
`firmware/prod/` writes against, and its whole value rests on one obligation: *the
document changes first, and the notification is explicit.* A silent pin swap between
revisions is how a week of bring-up gets lost to a problem that is not in the code at
all. That obligation was a promise. This makes it a gate: **the content hash and the
revision move together, or the build fails.**

It has already caught something in a smaller way — an edit to `WP-05.md` that I believed
I had made, and had not, because a string replacement silently matched nothing. Content
that changes without its revision moving is the same failure with worse consequences.

| File | Revision | SHA-256 of content |
|---|---|---|
| `board-rev-a.md` | 0.5 | `4b0c669a3d8655800ff9e1b6218ff63d571fb20b93082efa0a1f55135a7776ee` |
| `thermal-budget.md` | 0.2 | `087d0c460eecf9b9caacdfd6666a2c3836f4cedc4ac94603f65933b3e4db0578` |

`AUTO` rows are filled by `make -C hardware spec-bless`, which is the deliberate act of
recording that a revision bump is intended. The gate fails if a file's content hash
differs from the manifest **and** its revision has not changed — that is drift. A
revision bump with a new hash is a normal change and passes.

## What this does not do

It does not check that the `CHANGES` block is *accurate*, only that one was required.
A reviewer still has to read it. What it removes is the failure where nobody noticed a
change happened at all.
