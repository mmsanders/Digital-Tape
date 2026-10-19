# APP-1 host interface annex — APP-1A

**Issued by PM, 17 October 2026 PDT, ADR-185.** This closes APP-1 §3's interface
bindings. It governs the additive commands/flags only; existing no-flag commands,
exit meanings, audio/manifest bytes, engine and format remain unchanged. Independent
preflight/tests and exact-head disposition are still required before acceptance.
Basis: Software444/448 proposal59a868e; independent APP preflight fe8f3bdf.
The Software proposal's implementation-site map and capability probes are evidence,
not normative source or a licence to inspect uncovered implementation before authoring tests.

## 1. Diagnostic reports

`--report FILE --report-nonce N` occur together, at most once each. N is32 lowercase
hex digits generated randomly by the app per invocation. Invalid report options
exit2 on stderr without creating FILE. After parsing valid report options, create
FILE exclusively before other work/validation; other usage refusals may be reported.
An existing leaf, including dangling symlink/reparse point, is never followed or
overwritten. Creation failure exits1 before other work, with stderr only.
The app supplies a private per-job control directory distinct from DEST/stage/source/card.
An elevated child must bind that directory and exclusive leaf without traversing
substituted symlink/reparse ancestors. Failure refuses before device work. The
app deletes only its own marked directories, never a substituted foreign target.

Records are UTF-8 JSON objects, one LF-terminated line each, no insignificant
whitespace. Keys occur in the displayed order. Integer counters are nonnegative
and exactly representable up to2^53−1; existing checked input overflow rules apply.

| Record | Keys / meaning |
|---|---|
| start | `t,tool,version,nonce`; exactly one first; tool=`ingest`, `tapectl cards` or `tapectl make`; version pins the actual bundled executable/build |
| progress | `t,step,done,total`; optional, §4 |
| stderr | `t,text`; make only; exact diagnostic line without its LF, in original order; never selects a message/outcome |
| refusal | `t,id,subject` followed by the payload below; at most one terminal failure/refusal record |
| end | `t,exit`; exactly one last on a normal reporting path; equals actual process exit |

Stderr records may interleave with progress or precede end after refusal. Writes
need no durability flush. A failed/short report write (including start) stops report
writing, prints one diagnostic warning on stderr, and preserves the command's
ordinary outputs/exit semantics; successful publication remains success. Forced
termination may leave an incomplete report. No report file implies success.

The app ignores an unterminated final line. An absent/unreadable/empty report,
wrong tool/nonce/version, invalid record order, malformed/unknown record, unknown
ID for that tool/exit, invalid subject/payload/count or missing/mismatched end
cannot select an ID-specific message. Use actual child exit and generic failure;
ingest exit0 also requires its published pair as APP-1 requires. Report data never
turns nonzero/crashed child into success or authorizes a device. Missing optional
progress is valid. Show details uses raw captured stderr, or make's diagnostic
stderr records on platforms where elevation prevents pipe capture.

## 2. Ingest IDs, subjects and messages

Closed exit2 IDs:

- Request: `INGEST_USAGE`, `INGEST_LENGTH_INVALID`, `INGEST_TOO_LONG`, `INGEST_RIFF_LIMIT`.
- Folder: `FOLDER_SYMLINK`, `FOLDER_UNREADABLE`, `FOLDER_NOT_FOLDER`, `FOLDER_DUPLICATE`,
  `FOLDER_EMPTY`, `FOLDER_NAME_COLLISION`, `FOLDER_NAME_NOT_UNICODE`.
- Entry: `ENTRY_SYMLINK`, `ENTRY_NESTED_FOLDER`, `ENTRY_NOT_REGULAR`, `ENTRY_NAME_INVALID`.
- Source: `SOURCE_PROTECTED`, `SOURCE_NOT_AUDIO`, `SOURCE_TOO_SHORT`, `SOURCE_CHANGED`,
  `SOURCE_NON_FINITE`, `SOURCE_LEVEL`, `SOURCE_TRIM_UNSUPPORTED`,
  `SOURCE_OUTSIDE_INGEST1`, `SOURCE_CORRUPT`.
- Boundary/output: `JOIN_PEAK`, `JOINED_PEAK`, `DEST_EXISTS`, `DEST_APPEARED`, `DEST_NAME_INVALID`.

Closed exit1 IDs: `IO_SOURCE`, `IO_FOLDER`, `IO_DEST`, `IO_MEMORY`, `INTERNAL`.
IDs name the existing contract refusal/failure; they do not introduce admission
restrictions or change first-failure order. INTERNAL is a genuine tool failure,
not a replacement for any specified source/input refusal.

| Kind | subject | Display name |
|---|---|---|
| source / entry | `ordinal/NFC_name` | basename; for folder-content row use the dropped folder's name |
| folder | decimal ordinal string | that dropped folder's name |
| boundary | two neighbouring source logical paths in a two-element array | corresponding dropped folder name(s) |
| request/destination/internal | null | no invented source name |

Use existing INGEST logical-path rules; unrepresentable names identify their
folder, not a fabricated Unicode filename. SOURCE/IO_SOURCE and entry subjects
must identify the actual offending input. JOINED_PEAK may have null subject.
Payloads: INGEST_TOO_LONG has integer `total_frames,capacity_frames,excess_frames`,
with gaps included and excess=total−capacity≥1; FOLDER_DUPLICATE has `same_as`
(earlier ordinal string); JOIN_PEAK/JOINED_PEAK have six-decimal string `dbtp`.
Other IDs have no extra required payload. Exact fit succeeds; one frame over
reports1s using ceil(excess/44100);8467200 excess frames reports3min12s.

APP-1 §6 mapping:

- INGEST_TOO_LONG → exact overage; SOURCE_PROTECTED → protected-file row.
- SOURCE_CORRUPT/OUTSIDE_INGEST1/TRIM_UNSUPPORTED/LEVEL/NON_FINITE and IO_SOURCE
  → unusable-source row.
- SOURCE_NOT_AUDIO, ENTRY_NOT_REGULAR/NESTED_FOLDER/SYMLINK and
  FOLDER_SYMLINK/EMPTY → folder-contains-nonmusic row.
- SOURCE_TOO_SHORT/CHANGED, ENTRY_NAME_INVALID and FOLDER_NAME_COLLISION/NAME_NOT_UNICODE
  → named unusable-source/folder row.
- JOIN_PEAK/JOINED_PEAK and all remaining IDs → generic ingest failure, details available.

The app deduplicates known identical, nonsymlink folders by OS filesystem identity
before appending a drop; preserve first-drop order, perform no new child call when
nothing changes. Do not bypass symlink refusal, silently discard unknown inputs or
replace INGEST's own duplicate refusal. If identity cannot be established, INGEST
remains authoritative. Duplicate-folder refusal retains the generic row.

## 3. Tapectl IDs and terminal precedence

`cards`: exit0 enumeration completed (including no candidates), no refusal;
exit1 CARDS_ENUM_UNAVAILABLE with string `os_error`; exit2 USAGE.
Only aggregate offered/unprobed counts leave discovery for refused/unprobed disks.
Never publish a list of refused disk names.

`make` subjects are null. Closed outcomes:

| Exit | ID | Payload |
|---|---|---|
| 2 | USAGE, LABEL_INVALID, LENGTH_INVALID | none |
| 2 | WAV_INVALID | `reason`: open/riff/fmt/pcm/channels/rate/bits/align/data/chunk |
| 2 | DEVICE_OPEN_FAILED | string `os_error` |
| 2 | TOO_LONG | total_frames,capacity_frames,excess_frames |
| 2 | WAV_TRUNCATED | phase=load; may follow destructive start |
| 2 | NOT_PROVISIONED, P2_TOO_LARGE | preserve the underlying command's unreachable/guarded outcome; no artificial reachable test switch |
| 3 | REFUSE_NOT_WHOLE_DEVICE, REFUSE_NOT_REMOVABLE, REFUSE_TOO_LARGE, REFUSE_SYSTEM_DISK, REFUSE_FOREIGN_MOUNT, REFUSE_ERASE_NOT_CONFIRMED | optional unmount_failed=true only for failed own-p1 unmount |
| 1 | ENGINE | phase=provision/capacity/load/commit; result=existing TAPE_ERR_* name |
| 1 | IO | phase=provision/verify; op=entropy/read_lba0/clear_lba0/write_p1/build_mbr/write_mbr, only where applicable |
| 1 | VERIFY_FINDINGS | findings array in WP14 §4.1 emitted-line order |
| 1 | CARD_CHANGED | phase=safety/provision/load/commit/verify; string os_error |

Each finding is `{f:NAME}`; MOUNT additionally has side=A/B and result;
READ_ERROR additionally has side=A/B and integer frame. NAME is one of
MBR_LAYOUT,PARTITION_TYPE,PARTITION_TRUNCATED,MOUNT,NEEDS_REPAIR,SIDE_B_DEGRADED,READ_ERROR.
Preserve A-before-B and frame ordering, mount/read exclusions and no host TAPEFS parser.

On media-removal/change detection, stop immediately with CARD_CHANGED/exit1;
preserve stdout already emitted, emit no further normal findings/OK. Never erase
earlier observations. Otherwise verify frame-read errors are READ_ERROR findings,
mount errors are MOUNT findings, verify LBA0 I/O is IO, provision I/O is IO,
load/commit I/O is ENGINE/TAPE_ERR_IO. All remain exit1. Existing standalone
commands are unchanged. Make stdout is their ordered outputs, not report JSON.

Messages: provision ENGINE/TAPE_ERR_GEOMETRY and TOO_LONG → card-too-small;
CARD_CHANGED/device I/O/DEVICE_OPEN_FAILED → existing card-interrupted row;
VERIFY_FINDINGS → existing verify-finding row. WAV_TRUNCATED →
"The music file changed while the cartridge was being made. Start over and drop the folder again."
Do not claim the card is unchanged. Make exit3 →
"This card can't be used right now. Check the card and try again."
Other make failures → "The cartridge wasn't finished. Start over and try again."
Show details supplies diagnostics. Never mislabel truncated WAV as a card pull.
App-origin DROP_NOT_FOLDER/SPAWN_FAILED/ELEVATION_DECLINED/CARD_RECHECK_MISMATCH
retain APP-1's real OS/UI triggers; no forged child result or free-text parsing.

## 4. Progress

| Tool | Ordered steps | Unit / total |
|---|---|---|
| ingest | list,decode,convert,write,publish | folders/argument count; sources/source count for each pass; stage WAV bytes/(44+4*frames); publication/1 |
| cards | enumerate | disks probed / discovered disks, 0 while unknown |
| make | safety,provision,load,commit,verify_a,verify_b | safety/1; provision stages/4; frames/WAV frames; commit/1 (0 while unknown); frames/side total for each verify |

A step forms at most one contiguous block of progress records in that order;
done is monotonic, total is fixed or changes once from0 to known, and done≤total
when total>0. Counters describe work, not a required callback grouping or clock.
Emission is optional and may be sparse; the proposed1/64 cadence is an
implementation choice, not a new oracle. Bar weights may be1,4,60,5,15,15 for
make; record actual weights, use running maximum, never infer success from100%.
Checking-music bar is indeterminate until successful exact manifest facts or
INGEST_TOO_LONG facts; overage is full/too-long style. Progress never estimates overage.

## 5. Q6 — discovery is a candidate hint, authorization stays exact

Replace APP-1 cards output with `{t:"card",path:PATH,bytes:N}` per candidate and
`{t:"summary",offered:N,unprobed:M}` last. **Remove provisioned.** It is unused by
the UI and cannot truthfully mean exact recognition unelevated. Cards stays
unelevated, makes no writes/write-mode opens, never unmounts and never authorizes make.
Use OS enumeration/zero-access queries; the app itself never probes devices.

Require whole, removable-or-SD, nonvirtual, ≤128GiB, non-system/boot/swap facts;
unknown required safety facts count unprobed, never safe. No mounted volumes are
allowed except a possible own-p1 candidate recognized from OS partition views:
MBR partition style; p1 type0x0E/start2048/sectors32768; p2 type0xDA/start34816
to device end; no p3/p4 and no other mounted volume. OS-visible boot/system use
always excludes. Missing CHS/raw boot-sector fields are not invented. Unknown
OS-view extents/types cannot earn that discovery exception. Bare cards with no
mount may be candidates. This is expressly weaker discovery, not WP14 exact layout
or its destructive mounted-partition exception. A plausible but byte-invalid card
may appear, then be refused by make with zero writes.

Make retains all exact WP14 safety/layout/own-p1 checks before destructive work;
no discovery hint waives them. "One open" means one authorized device session
across provision/load/verify, no reopen to resume on a new path. Preliminary
read-only/zero-access safety query handles are permitted; WP14's policy-refusal
zero-write/zero-write-mode-open rule is retained. A capability/race conflict is
returned at independent preflight before S2/S3 implementation, never solved by
silently weakening that rule. Existing commands/ports keep their accepted semantics;
a separate read-only discovery helper is allowed in host code, not engine code.

## 6. Platform capability and acceptance holds

Known removal errors/count/disappearance may establish CARD_CHANGED; ordinary EIO
alone is device I/O, not proof of replacement. Never reopen after failure. An
undetected swap inside a reader or equal-size pre-launch gap remains a disclosed
limit, never inferred from image/VHD tests or path+capacity. Native controls must
bind actual error/lifetime/zero-foreign-write observations.

G1 runtime requires process-attributed detection of actual device-open attempts,
including failed, transient and zero-access opens; ordinary-file positive controls
must remain clean. Qualify a candidate method against those controls before using
absence of records. Handle sampling or app self-logging alone cannot establish
absence. Windows in-box tracing failed controls; Procmon or another ordinary-settings
method may be evaluated, not presumed adequate. Mac fs_usage catches paths only
on the submitted SIP-disabled runner; SIP-on proof remains held. No security change,
injection, shipping seam, rebuilt tapectl, purchase or new Michael test is licensed.
Prompts/declines and actual Windows11/macOS family builds remain independently
unobserved where disclosed. Host authoring/build work may proceed while these
native acceptance gates stay held. G2 waits for accepted dependencies.

## 7. S3 boundary queries and device binding — ADR-189

These rules apply only to additive `tapectl make`, not existing standalone commands.
A required initial safety, authorization or object-binding query must succeed before
any write-mode device open or destructive work. Unknown facts never become safe.
Known policy refusals retain WP14 exit3 and zero writes/zero write-mode opens.
An ordinary OS failure of a query required to establish those facts stops with the
host outcome below; it is not evidence of replacement and is not an engine error.

Add the closed make exit1 ID `HOST_QUERY_FAILED`, subject=null, required payload
`phase=safety/provision/load/commit/verify`, `op=media_query`, string `os_error`.
Phase names the boundary where the failed query was attempted (before provision is
safety). The app uses the existing card-interrupted row and exposes raw diagnostics.
Do not change existing IO phase/op bindings or synthesize TAPE_ERR_* for a host query.

Additional post-authorization media monitoring is optional: this decision prescribes
no new query/callback cadence. It cannot replace required initial checks, retained
session identity or OS-reported removal/change detection. If performed, an ordinary
failed media query is fail-stop HOST_QUERY_FAILED, never ignore-and-continue;
positively detected removal/change remains CARD_CHANGED. Stop subsequent work,
retain earlier stdout/report/publication facts, never roll back an already committed
phase or claim the card unchanged, and never reopen the path. A report-write failure
still obeys §1 and cannot suppress the ordinary child outcome.

Windows/macOS S3 device-session methods remain HELD. The tested access upgrades and
post-path-open identity checks do not establish binding before authorized write-mode
access; no weaker guarantee is adopted. Linux retained-inode/diskseq loop receipts
are only bounded capability facts, not S3 acceptance or proof that an access upgrade
cannot reach changed media. Any platform must first obtain independent method/test
clearance under §5; other platforms need not wait for it. No speculative API-search
campaign is issued. S2 and other issued host evidence work continue independently.
