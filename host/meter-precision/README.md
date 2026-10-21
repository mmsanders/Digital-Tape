# Software513 test-only exact-function observations

Method254 is imported unchanged before this implementation. The source builder
extracts common/dsp/convert/observe/mem from pinned b9f430c8; asserts the issued DSP
SHA256; retains original hashes and an explicit insertion list. It adds trace
calls, a local boolean equivalent to the original refinement conditional, and
private at/grid4/coefficient access in the same module. Production source in the
repository, its arithmetic and the shipping CLI are unchanged.

Only join-29000-1, gap-1 and block-end-1 original inputs/outputs are used. Original
WAVE PCM16 payloads are passed through production deinterleave and conversion;
this observes the conversion function with lossless zero trim, and does not claim
a new shipping decoder receipt. Each source occurrence has its own conversion.
Original quantize resets Xorshift::new per source and per attempt. All actual gain
attempt scalars are retained as IEEE little-endian bytes. The unchanged independent
quantizer model is extracted and SHA authenticated from the original accepted
source; its exact-real rounding is compared separately, without tuning discrepancies.

The fixed finite boundary/phase/neighbour set is applied to original assembled
PCM, in both channels. grid4 returns absolute values: compare to abs(at) at the
same four phases, not signed at. Each support hash binds the 512 retained f32
samples with zero extension. Full streamed histories run last. Trace events retain
every meter range, every running-maximum change and every refinement decision;
unchanged noncandidate history is recoverable from exact input and original loop.
This is finite instrumented evidence, never global peak/transfer/absence proof.

A252 recorder source is unchanged. A Python helper emits its fixed PID/nonce/
input header and fixed success streams, and invokes one native operation into a
fresh separately manifested domain directory. The external recorder input binds
native argv, executable/source and all input hashes; the domain manifest binds
actual native PID/argv/stdout/stderr/exit/timing/trace/output. Native failure or its
four-second timeout preserves that domain plus incomplete recorder raw and stops
the activation. No unchanged retry or recorder timeout extension is permitted.

The opened-only workflow records ordinary hosted build/runtime and runs once.
600 CPU-seconds reserve includes build and supervision (build must consume <540),
7200 cumulative CPU/512MiB total new working and evidence bounds apply. Storage is
checked including target, source, input and raw before every native operation.
Returned ZIP/loose original artifacts survive even on failure. No old500 endpoint,
shipping CLI, audio search, fault or observer/capture operation is invoked.
