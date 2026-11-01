/*
 * makereport.h — `tapectl make`'s diagnostic report (APP-1A §1, §3, §4).
 *
 * The same record grammar as report.c, which `cards` keeps using unchanged, plus
 * what the ELEVATED make child needs: the report's parent directory and every
 * ancestor are bound before the leaf is created (never through a symlink or
 * reparse point, and the parent held open until the end so nothing in the chain
 * can be renamed), progress records the app can read while the child runs, and
 * stderr mirrored into stderr records, because the app cannot pipe an elevated
 * child's stderr.
 */

#ifndef TAPECTL_MAKEREPORT_H
#define TAPECTL_MAKEREPORT_H

#include <stdint.h>

/* Bind FILE's directory chain, create FILE exclusively (never following an existing
   leaf) and write the start record. Returns 0, or -1 with the reason in
   mreport_error(); nothing is created then. */
int mreport_open(const char *file, const char *tool, const char *version, const char *nonce);
const char *mreport_error(void);

/* Records; each is a no-op without an open report or once writing has stopped.
   A failed write stops the report and warns once on stderr. */
void mreport_progress(const char *step, uint64_t done, uint64_t total);
/* subject null, then `payload`: "" or a JSON fragment of further keys in order,
   e.g. ",\"phase\":\"load\"". */
void mreport_refusal(const char *id, const char *payload);
void mreport_stderr(const char *text);
void mreport_end(int exit_code);

/* From here until mreport_release_stderr, every line written to stderr also
   becomes a stderr record, in order, and still reaches the original stderr.
   No-op without an open report. */
int mreport_capture_stderr(void);
void mreport_release_stderr(void);

#endif /* TAPECTL_MAKEREPORT_H */
