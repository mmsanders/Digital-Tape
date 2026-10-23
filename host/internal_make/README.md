# Internal retained-file composition candidate

Issued completion: Product557 / Verification299 under PM554. This is unreachable from
shipping tapectl/app callers. No shipping Make/device/image command or flag is added.

The core borrows a caller-owned session for provision, load, commit and read-only
verify. Host operation bodies are extracted from existing tapectl; the engine and
format remain unchanged. Reference build includes exact mainbf2381c9 tapectl/target
bodies, with only declared test-only existing-zero-file admission substituted for
the original sparse-creating image admission. It does not test that old create path.

Independent292/a901272c freezes ten-row same-input whole-image/stdout/exit/session
predicates.302/420e5cf3 adds existing/materialized/non-reparse twin admission and
matched actual copied-handle I/O faults. Modeled query/change/removal facts do not
establish Windows/native sensing.

build.sh compiles two exact source-bound adapters; it never executes them. Local
one-attempt600s admission and closed actual raw inventory are still required before
a runtime return. Compilation is not acceptance. No actual UI/native/session/A6/
S3/fullAPP/INGEST/G2 or Make clearance follows.

Chronology limitation: unpublished local port scaffolding existed before302, was
quarantined without build/run/publication, and was disclosed in299 comment6371062146.
The final port was constructed after reading302; that does not rewrite the earlier
authoring chronology. See docs/REVIEW/software557/PORT-CHRONOLOGY.json.
