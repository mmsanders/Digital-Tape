# Independent closed-ID reachability boundary

Domain: issued INGEST-1 finite IEEE64 includes nonzero values far below binary32's
least positive subnormal, since no minimum nonzero float amplitude is specified.
At44100Hz one decoded source frame gives one output frame. Thus canonical one-frame
mono float64 sample1e-300 is neither nonfinite, digital silence, zero-frame nor an
unsupported format. The contract explicitly requires valid source true peak unless
silent, otherwise named refusal. With AP4's declared binary32 true-peak inputs, it
rounds to0, providing a concrete SOURCE_LEVEL witness, alongside0 (silent) and
1e-30 (nonzero representable, unmeasurable short) valid neighbours. run_ids.py checks
real child/report evidence; this is not a synthetic failure switch or new minimum
admission rule. The witness is bounded to pinned AP4/source/build.

DEST_NAME_INVALID: an actual empty string supplied as --out value is a concrete
invalid destination name, different from absent --out (usage) and an existing root
(DEST_EXISTS). Current b9f430c parse accepts the empty PathBuf, check_dest sees no
leaf and existing current parent, then publication's file_name() has none. There
is no need to invent a fake destination guard. run_ids.py preserves that empty argv
and pairs the same admitted source with a valid fresh destination.

INTERNAL: decode-plane/output-length consistency and finite gain-refinement failure
are genuine implementation invariants/tool failures, not required refusal inputs.
No valid input in these four witnesses justifies forcing that ID. Their bounded
silence/one-frame representable cases have fixed frame counts and unmeasurable
loudness, so no finite-measured gain oscillation is introduced. This is NOT a global
proof over all arbitrary finite supported streams/decoder states; that branch
remains unobserved/unproven. Software may return a rigorous invariant proof or a
real admissible defect, never a shipping fake-ID switch.

JOINED_PEAK: source isolation and every join/gap are checked before the final joined
predicate. A useful proof must show the streamed reconstruction's evaluated points
and rounding/refinement are bounded by the earlier per-source and boundary checks,
including finite filter support and block boundaries. Merely saying 'all joins
already checked' is insufficient: adaptive true-peak refinements/block coordinates
must be related. No global numeric equality/unreachability theorem is claimed here.
The single-source silent/quiet neighbours do not create a multi-source boundary;
that bounded input subset is covered by existing one-source measurement predicates.
Other arbitrary-input/global JOINED_PEAK reachability remains explicitly UNPROVEN
pending466's argument/evidence. Do not force INTERNAL or add an input restriction
as a substitute. No normative ambiguity requiring PM is newly asserted by this map.
