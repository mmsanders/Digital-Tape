/*
 * report.h — the opt-in diagnostic report (`--report FILE --report-nonce N`).
 *
 * Normative: docs/WP15-APP-ANNEX.md §1 and docs/WP15-APP-CONTRACT.md §3.
 * FILE is created exclusively before other work and never followed when it
 * exists (including a dangling symlink or reparse point). Records are one JSON
 * object per LF-terminated line, keys in the issued order. A failed write stops
 * report writing, prints one warning on stderr and changes nothing else.
 */

#ifndef TAPECTL_REPORT_H
#define TAPECTL_REPORT_H

#include <stddef.h>
#include <stdint.h>

/* Is `n` 32 lowercase hex digits? */
int report_nonce_ok(const char *n);

/* Create FILE exclusively and write the start record. Returns 0, or -1 with
   the OS's reason in report_error() and nothing written. */
int report_open(const char *file, const char *tool, const char *version, const char *nonce);
const char *report_error(void);

/* report_open for the elevated make child (APP-1A §1): FILE's parent directory
   and every ancestor are bound first, without following a symlink or reparse
   point, and the parent is held open until report_end so it cannot be renamed
   or replaced; then the leaf is created exclusively in it. A substituted
   ancestor fails here, before any device work, and creates nothing. */
int report_open_bound(const char *file, const char *tool, const char *version, const char *nonce);

/* Records; each is a no-op when no report is open or writing has stopped. */
void report_progress(const char *step, uint64_t done, uint64_t total);
void report_refusal_os(const char *id, const char *os_error);   /* subject null, os_error string */
void report_refusal(const char *id);                            /* subject null, no payload */
/* subject null, then `payload`: "" or a JSON fragment of further keys in order,
   e.g. ",\"phase\":\"load\"". */
void report_refusal_payload(const char *id, const char *payload);
void report_stderr(const char *text);                           /* make: one diagnostic line, no LF */
void report_end(int exit_code);

/* make: from here until report_release_stderr, every line written to stderr
   also becomes a stderr record, in order, and still reaches the original
   stderr. The elevated child's stderr cannot be piped to the app (APP-1A §1).
   No-op without an open report. */
int report_capture_stderr(void);
void report_release_stderr(void);

/* Append `s` as a JSON string (quotes included) to buf; returns bytes needed. */
size_t report_json_string(char *buf, size_t cap, const char *s);

#endif /* TAPECTL_REPORT_H */
