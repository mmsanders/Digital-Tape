# Independent S3 feasibility boundary

APP-1A §5 resolves the former apparent one-open/refusal conflict: preliminary
read-only/zero-access queries are allowed; one authorized session remains across
provision/load/verify, and verify binds NULL write. No normative contradiction
at that abstract interface is newly identified. Earlier196 preflight/Q1–Q7 carries.

This does not establish a real platform method. Software465 must return its exact
proposed ownership/handle algorithm and already available or harmless RO capability
observations BEFORE S3 implementation. Required method table:

1. Which process owns each query/authorized handle and when it opens/closes it;
   all pre-policy handles lack write access, every refusal has zero writes and
   zero write-mode opens. How exact mounted-own-p1 bytes are obtained read-only;
   no unmount based merely on OS partition hint or bare CRC55AA.
2. How the safety decision remains bound to the authorized object, accounting for
   the query-to-authorized-open interval. Path+capacity alone is insufficient.
   Rechecking only AFTER a write-mode open cannot prove that open never happened
   on a policy-refused target. State concrete OS ownership/locking assumptions,
   observed races/limitations and which image/native scope they support. Do not
   silently weaken refusals or claim unobservable reader swaps are detected.
3. How exactly one retained authorized session calls the existing engine commands,
   and exposes NULL-write verify without reopening its device path. Detection of
   OS removal/change terminates work, never retries/reopens on replacement.
   Ordinary EIO stays IO unless actual OS removal/change facts justify CARD_CHANGED.
4. How elevated report-directory identity and exclusive no-follow leaf are bound
   against substituted ancestors, and cleanup never follows a foreign target.
   Actual harmless file/directory/reparse controls can test this without a card.
5. The paired test-only image/loop/VHD route under existing TAPECTL_TEST semantics,
   actual shipped virtual refusal, native trace source/control qualification,
   platform/build constraints and precise unexecuted reader/elevation scope.

No new port/engine hooks or shipping fake facts are licensed. If the exact method
cannot meet a platform's rules, hold that platform/slice for PM with concrete
observations and continue S2/209/210. No new human or security-change request.
No running raw disks or device probes is needed for this paper preflight. This
publication deliberately does not claim native feasibility from unobserved APIs.
