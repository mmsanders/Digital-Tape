# Rig method expectations awaiting a declared interface

Derived from WP-05 A-6 and R374-1…5, Product cc23b87f, before corrected code.
These are required cases, not executed tests or a newly invented schema.

| Input/control | Required outcome |
|---|---|
| Otherwise valid payload/response/busy record, actual opening inside busy after accounting for declared instrument and switch uncertainty | May count once; requires method-supported wire/rail evidence, never merely a GPIO command timestamp |
| Busy ends between last low sample and actual opening | Non-qualifying; retain readbacks and classify every otherwise valid returned target/neighbour |
| Arbitrarily stale sample, no evidence covering actual opening | Cannot count as proven busy-at-opening; absence of a deassertion field is not proof |
| Edge/busy uncertainty intervals overlap so ordering cannot be determined | Ambiguous, non-qualifying; preserve reason/raw identity |
| Requested cut is delayed until after busy ended | Non-qualifying even if request timestamp was inside busy |
| No actual rail opening, missing waveform/actual-edge observation, or failed cut | No qualifying credit; preserve failure and any returned corruption |
| Valid late miss + 1,000 proven qualifying rows | Late row adds zero credit; lawful OLD/NEW with intact neighbours does not suppress a valid aggregate |
| Same miss, target mixture/other bytes or any neighbour damage | Block PASS and retain exact offending iteration/location even when 1,000 other cuts qualify |
| Before/after CID differs, missing CID, changed immutable calibration/firmware/plan or trace identity | Reject/invalidate identity evidence; do not infer continuity from card label |
| Missing/malformed required row/trace, duplicate identity, missing neighbour baseline | Incomplete/invalid run; never manufacture qualifying count |

No numeric maximum sample age, comparator threshold or dead time is selected here.
Hardware's declaration must define units, edge meaning, uncertainty intervals,
trace/calibration and binary hashes, before/after raw CID, failed/missed-attempt
representation and summary fields. Declare these publicly before implementing
their checker behavior. Bind the cases to that declaration in a new publication.

R374-3/4 additionally require primary-part specifications and worst-case timing,
drive/discharge/current/back-power analysis. Synthetic judge results cannot prove
electrical safety or replace measured delayed/no-cut controls. R374-5 remains
SPI-only characterization; no transfer to native SD4/SDR50 qualification.
