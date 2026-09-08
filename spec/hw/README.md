# Hardware specification — versioned, not format-frozen

Owner: Hardware Lead. Revisions/hashes are in [VERSION.md](VERSION.md).
Generated tables must agree with their source and the hardware manifest.

| File | Consumer / obligation |
|---|---|
| board-rev-a.md | Firmware; notify Software of pin/rail/timing changes with a concrete change list |
| thermal-budget.md | Safety design and audit; label estimates, record method/raw data/uncertainty for measurements |
| cartridge-shell.md | CAD and physical trials; geometry/model checks do not establish measured durability |

Routine hardware revisions need notification, not separate PM approval. Changes to
product limits or guardrails do require PM disposition. Safety limits live upstream
in spec/acceptance.md; they cannot drift with a model.

No board fabrication or cell charging while the fabrication gate is CLOSED.
Independent acceptance is not supplied by a generator, manifest, or the response author.
