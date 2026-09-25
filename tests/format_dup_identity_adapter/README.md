# R29 format/duplicate product binding

Software-owned mechanical binding for the verifier-owned
`tests/format_dup_identity_draft8/` tree.

The binding authenticates exact tree
`bd81f66d515c4f71e03efc6edd55f70d1d0383da`, executes the real public C API,
models only raw block-device durability/injection, and emits raw bytes/public call
facts. It does not import or call the verifier oracle.

The C worker receives the exact raw destination bytes produced by the verifier
fixture module. Its dual working/durable sparse block images implement
`flush_required` and `write_through`; the Python streaming adapter supplies only
the verifier protocol and raw observations.

If a canonical case fails, the verifier runner retains
`failure-reproducer.json`. Per #226, Software classifies that first failure before
any engine change and does not skip ahead to later cases.
