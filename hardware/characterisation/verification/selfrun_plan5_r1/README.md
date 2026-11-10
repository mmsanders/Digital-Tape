# V405 selfrun-r1 / plan5 bindings, r1

Independent author: Verification. Input Hardware675/PR673 correction2 at8f31d5897e079c5c3fb1870db3d76491e11dcd28, POWER-CUT-SCHEMA-R1 §0–§7; issued ADR209 Product21b2da370c8ba2593a7a9fc1d5d52ec62d1160a4. No new judge or physical-cut firmware implementation inspected. All generated photos, builds, logs and rows are labeled SYNTHETIC and prove no real card, time or witness.

**180 declared executable CLI cases:**111 row/qualification/verdict cases,41 plan/continuation cases,23 serial/build/hash/normalization controls,5 plan-integrity/mixed-version cases. CATALOG.json records their coverage. Six predicate controls detect blanket outcomes, erased completed-OLD, null-CID gating, dropped CID disagreements and hidden qualifying damage.

Selftest: `python -B tests/selfrun_plan5_r1/run.py --selftest --out NEW_DIRECTORY`.

Returned implementation: `python -B tests/selfrun_plan5_r1/run.py --judge PATH/media_atomicity.py --out NEW_DIRECTORY`.

Selftest checks the111 independent expected row outcomes and control predicates. It does **not** execute a Product CLI. The --judge mode invokes the actual declared plan/judge CLI for all180 cases, validates typed output/explicit reasons where declared, producer/build/hex/raw/normalized byte linkage, normalization text/order, metadata and retained SPI residual scope. Every fixture has1001 distinct attempts (1000 qualifying plus a retained completed-NEW miss), production minimum1000; there is no tiny Policy injection. Raw output under work/ is regenerable synthetic case input, overwritten between cases; RESULT.json keeps case results. Never use that directory as a physical campaign archive.

Plan generation authenticates real fixture photo bytes and permits null retail part/CID; continuation retains unit/model/run/build/schedule context. Qualified/missed damage and completed OLD are independently separated; equality at5us/200mV and ended-before equality follow ADR209. Malformed data is a run problem or strict input refusal as declared, not a successful logical observation. Present/missing/disagreeing valid CIDs remain diagnostic only. Missing/unknown row keys are not accepted as policy overrides.

Import this directory unchanged in a distinct commit before implementing the new host-side route. Do not import oracle.py as Product implementation or tune its values/assertions. Preserve v3/v4/rig-r2 and every old imported package. This licenses only the bound host-side plan/judge/build/normalization behavior; physical characterisation firmware needs its own public declaration and independent bindings.

The caller/record boundary is [RECORD-CHECK.md](RECORD-CHECK.md). All wrapper outputs accepted:false/physical_run:false. A later genuine >=1000-cut independent/Michael record may satisfy A6 within ADR209's declared SPI/model scope; this publication supplies no such record or physical authority.
