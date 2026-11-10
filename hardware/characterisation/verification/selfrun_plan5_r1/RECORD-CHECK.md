# Per-run record boundary (manual independent check, not a new Product schema)

The host judge's declared interface consumes raw serial, build.json and exact hex bytes; it does not read or author MICHAEL-CHECKS. For each future physical run Verification must compare the genuine entry against the original files:

- Date and Michael's actual card-unit label; model/part-or-unknown/capacity/photos/back-print/run identity. CID is diagnostic, never fabricated or required.
- firmware_build and hex_sha256: plan, BUILD line, every validated row and build.json agree; exact hex bytes authenticate.
- plan_digest, serial_sha256, run_jsonl_sha256 and verdict.json SHA256 all match retained bytes. Normalized rows are exactly ATOM-prefix removal with the declared LF/CR handling, in input order.
- qualifying, vcard_off_mv_max and sample_to_cut_us_max transcribe the actual verdict. At least1000 distinct qualifying cuts, zero torn/corrupt/neighbour damage and completed_before_old empty; all attempts and failed controls stay retained.
- Michael's actual note, actual SPI/speed, self-observed timing/off voltage and one-unit-per-model residual limitations. No nativeSD4/throughput or other-card claim.

No record key or fake Michael entry is invented here. The declaration lists these human record fields but supplies no Product JSON/checker API for the entry. New machine checking of that record requires an explicit declaration/binding; copying synthetic fixture labels into a real sign-off is never evidence. Target firmware and N3–N5 physical controls remain unexecuted.
