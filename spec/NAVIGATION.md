# spec/NAVIGATION.md — read two sections, not 217 KB

**This file is a navigation aid. It is not normative and it is not part of the frozen
bundle.** The three frozen files — `spec/tapefs-v1.md` (103 KB), `spec/engine-api.md`
(67 KB), `spec/acceptance.md` (47 KB) — are DRAFT-8 at the hashes recorded in
[VERSION.md](VERSION.md) and are **never edited, reformatted or annotated**, including
by this file. Line numbers below are valid only at those exact hashes; if the `spec`
CI job is green, they are valid.

Read the sections your tranche touches:

```sh
sed -n '122,344p' spec/tapefs-v1.md     # superblock and mount
```

If this map and a frozen file disagree, **the frozen file wins** and the disagreement
is a finding, not an edit.

## By package

| Package | Read first | Then |
|---|---|---|
| WP-06 block device, superblock, index commit | `tapefs-v1.md` §3–§5 (98–471) | `engine-api.md` §3 device (65–106), §5 lifecycle (142–237) |
| WP-07 chunk allocator, copy-on-write Side B | `tapefs-v1.md` §6 chunks (472–479), §7 ownership and allocation (480–508), §8 commit (509–547) | `tapefs-v1.md` §9.2 reset Side B (566–575); `engine-api.md` §9 cartridge operations (432–492) |
| WP-08 playback, seek, variable-rate scrub | `engine-api.md` §6 transport (238–338) — §6.2 advance and §6.3 render loop are the normative pair | `engine-api.md` §8 exact audio arithmetic (393–431); `tapefs-v1.md` §5.1 entry runs (368–411) |
| WP-09 record: overwrite, overdub, splice | `tapefs-v1.md` §9.1 (550–565), §8 commit protocol (509–547) | `engine-api.md` §7 recording (339–392), §7.1 synchronous commit, §7.2 `TAPE_ERR_FAULTED` |
| WP-10 crash-injection harness | `tapefs-v1.md` §8.1 durability convention (524–547), §4.6 superblock write order (316–344) | `acceptance.md` WP-10 (38–84) |
| WP-11 goldens and runner | `acceptance.md` WP-11 (85–114) | `engine-api.md` §8 exact audio arithmetic (393–431) |
| WP-12 re-spool / defragment | `tapefs-v1.md` §9.4 (679–704) | `tapefs-v1.md` §7 ownership (480–508) |
| WP-13 embedded-readiness audit | `engine-api.md` §4 memory (107–141) | `engine-api.md` §13 what the engine must never contain (604–611) |
| WP-36 slot capability model | `tapefs-v1.md` §4.3 effective writability (228–243) | `engine-api.md` §3.1 the one permission predicate (91–106), §10 state matrix (493–537) |

## By undefined entry point

The five declared-and-undefined public symbols and their normative text:

| Symbol | Normative section |
|---|---|
| `tape_promote` | `tapefs-v1.md` §9.3 promote Side B to Side A (576–678) — the longest operation section |
| `tape_respool` | `tapefs-v1.md` §9.4 re-spool (679–704) |
| `tape_dup` | `tapefs-v1.md` §9.5 duplicate (705–777) |
| `tape_format` | `tapefs-v1.md` §9.6 format (778–820) |
| `tape_abort` | `engine-api.md` §9.1 the incremental contract (454–482), §9.2 the operations (483–492) |

## By topic

| Topic | Where |
|---|---|
| The three governing rules | `tapefs-v1.md` §0 (19–28) |
| Constants and tape lengths | `tapefs-v1.md` §1 (29–52), §2 (53–78); geometry predicate §2.1 (79–97) |
| Mount, four phases, only the last writes | `tapefs-v1.md` §4.1 (158–209) |
| Index selection and the stage oracle | `tapefs-v1.md` §4.2 (210–227) |
| Effective writability (Guardrail 06) | `tapefs-v1.md` §4.3 (228–243); `engine-api.md` §3.1 (91–106) |
| Degraded-B, counter headroom | `tapefs-v1.md` §4.4 (244–265), §4.5 (266–315) |
| Index slot, entries, slot validity, timeline cap | `tapefs-v1.md` §5–§5.4 (345–448) |
| Cartridge sequence | `tapefs-v1.md` §5.5 (449–471); exhaustion §10 (821–830) |
| Side A ownership, `a_high_water` (Guardrail 05) | `tapefs-v1.md` §7 (480–508) |
| Durability and permitted crash outcomes (Guardrail 07) | `tapefs-v1.md` §8.1 (524–547) |
| Error codes | `engine-api.md` §2 (28–64) |
| Memory budget (Guardrail 08) | `engine-api.md` §4 (107–141) |
| State matrix, boundary semantics, invariants | `engine-api.md` §10–§12 (493–603) |
| Engine prohibitions (Guardrails 09, 12) | `engine-api.md` §13 (604–611) |
| What the cartridge does not store (Guardrail 03) | `tapefs-v1.md` §11 (831–842) |
| Instant-on is not a format feature (Guardrail 04) | `tapefs-v1.md` §12 (843–855) |
| Media atomicity — the one physical assumption | `acceptance.md` (141–152) |
| Hardware safety limits, PM-owned | `acceptance.md` (153–167) |
| **Freeze scope and what is still open** | `tapefs-v1.md` §14 (866–877); `engine-api.md` §14 (612–625) — read these before assuming a behaviour is frozen |

## Not in the frozen bundle

`spec/hw/` is versioned, not frozen with the byte format; see
[CLAUDE.md §5](../CLAUDE.md). Test-package copies of spec bytes under `tests/*_draft8/`
are authenticated historical inputs held by tamper controls — never deduplicate them
against `spec/`. An API absent from the spec is a finding, not something to invent.
