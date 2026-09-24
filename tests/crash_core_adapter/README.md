# WP-10 core crash product binding

Software-owned mechanical binding for the immutable verifier package at
\`tests/crash_core_draft8/\`.

The verifier stream terminates in \`adapter.py\`. It parses only the verifier-owned
case envelope and forwards it to a persistent C worker through a fixed tab-delimited
internal protocol.

\`wp10_core_worker.c\` links the unchanged product engine archive and uses only the
public API. Its block device keeps distinct working and durable byte images:
reads observe working; ordinary writes update working; write-through writes also update
durable; successful flushes copy working to durable; torn writes land the exact selected
prefix into both; and after-write cuts are fired at the following flush before that
flush changes durability.

The worker establishes one real clean product baseline per verifier scenario/seed,
then runs each requested injection from a fresh verifier fixture. Post-crash mount uses
a fresh engine instance initialized from durable bytes only. Compact snapshots are
emitted from raw durable media; no old/new/safe classification is produced by Software.

This binding changes no engine or verifier-owned byte. A red product run is retained
as the verifier's first compact reproducer and is a stop condition for #211.
