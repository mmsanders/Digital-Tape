# Verification evidence records

**Every file in this directory is a dated evidence snapshot.** Run READMEs and dispositions
describe state on their own dates; statements such as "PR #20 remains held" or "PR #77 stays
draft" are not current (#77 merged at `4e1d248`; #20 closed without being merged). The files
are left byte-unchanged because dispositions cite them and two run directories contain
pinned evidence bundles declared in [tests/IMPORTS.json](../../tests/IMPORTS.json).

Current integration state is in [verification integration](../VERIFICATION-INTEGRATION.md)
and [STATUS](../STATUS.md). Raw observations over 1 MiB live in release `evidence-2026-09`;
run `tools/fetch-evidence.sh` before replaying a retained bundle.
