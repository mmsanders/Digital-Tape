# ADR-170 continuation preflight

P2READ-001 is resolved by Product #410, merged
`5e6d5fd6cfce64031ba12b37fc367145b5fe18dd`, exact revised public source
`26d3cb320ac6ce76dd2e26e22e1af4d4e7c0adbf`. The previous PREFLIGHT.md remains a
historical #151 checkpoint; its unresolved language is superseded by this document.
INPUTS.json carries its source/merge/tree and hashes explicitly.

All five previously derived C60 arithmetic rows remain valid. ADR-170 adds finite
mapping/seek/episode and idle inequalities without changing DRAFT-10, volume/call,
copy/movement, arithmetic, callback or resource limits. No new contradiction was
found in the independent paper/fixture preflight; no Product implementation/design/
private-test inspection or candidate observations informed expectations.

The executable max-E fixtures are valid disjoint physical intervals:

- Short: E=4096 entries, one frame each, physical stride 129 frames. Every entry
  maps distinct content, including shared chunks and unaligned block edges.
- Long: E=4096 entries, 256 frames each, physical stride 384 frames. S=4,194,304,
  useful payload B=8192 blocks before allowed alignment/prefetch overhead. The
  issued V ceiling at B=8192 is 49,184, while the actual forced full-scan control
  costs 33,554,432 inspections. Its failure remains non-vacuous under the allowed
  additional requested-block ceiling as well.
- All fixture nominal lengths/chunk counts use the frozen ceiling formula; C60
  uses nominal=3600, total_chunks=1212, exact logical S=635,040,000. All superblocks,
  selected indices, CRCs, extents and disjointness are independently built/checked.

No particular buffer layout, watermark or prefix array is mandated. A monotone
cursor and bounded entry lookup are sufficient feasibility witnesses for the finite
work limits without increasing the caller's fixed 65,536-byte rings or requiring
engine heap storage. This is paper feasibility only: actual unchanged RAM <=200 KiB,
stack <=8 KiB, rodata <=32 KiB and no-allocation/no-extra-funnel gates remain READ-2.

Per-command counter deltas cover setup in seek/side/rate/content/warm/mount episodes;
the cold global reset follows mount. Source-binding audits must distinguish playback
mapping from mount-selection validation and count all playback helper loops on idle
paths without name filtering. The event trace originates in the independent backend,
not adapter-supplied totals. Requested counts include failed/redundant callbacks.

Full int32-rate cases retain underrun and frozen endpoint semantics instead of
requiring an impossible 128-frame extreme-rate span to fit the ring. Fractional
lookahead, same-side invalidation, incomplete-read poison and old-content controls
are explicit. No bounds are fitted to a candidate, no tolerance is accepted, and
no unchanged WP14 C60 timeout run is requested.

READ-1 stop is the complete immutable merged executable publication and direct
handoff to Software #409. READ-2 cannot start without its separate held Product
head/import and actual evidence. #146 remains open; all WP14/native/platform/
physical/release/hardware/merge holds survive.
