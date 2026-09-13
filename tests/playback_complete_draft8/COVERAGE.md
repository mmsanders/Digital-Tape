# P1-R6 coverage and exclusions

Ten families cover: empty at zero and nonzero rates; non-empty stopped at an interior
position; one frame at `INT32_MAX`; reverse from zero; reverse at `INT32_MIN`; exact
forward and mirrored-reverse 16-row scrubs; and side switch from Playing and idle.
Assertions bind zero/short counts, `TAPE_OK` versus underrun, tell/status/info state,
endpoint clamps, every signed rate and render subdivision, service completion, rate
retention, position/flags/warm reset, ring invalidation, first Side-B PCM, and complete
callback legality. Candidate scrub output is 88,200 stereo s16le frames per direction.

Targeted mutations: empty-check ordering; zero-rate drift; INT32_MAX overshoot;
reverse-from-zero skip; INT32_MIN wrap; changed scrub rate; changed scrub row count;
reverse start; service-time-as-render-time cadence; side-switch refusal while Playing;
position retained; endpoint flag retained; warm flag retained; rate lost; stale Side-A
PCM. Package/spec/WP-08/fixture/PCM tamper, adapter identity/provenance/exit/timeout,
nonempty-destination and offline replay controls are also exercised; the earlier
P1-R4 self-test remains mandatory and unchanged.

Excluded: product implementation/adapter inspection, any real engine run or result,
accepted golden/listening disposition, warm-descriptor negatives, recording,
crash/recovery, long-operation/state-matrix completion, performance, hardware/cards,
purchases, fabrication, charging, and any frozen-spec change.
