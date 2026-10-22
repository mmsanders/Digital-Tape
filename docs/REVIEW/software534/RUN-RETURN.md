# Software534 local Windows no-card test return

Product base:75f867712138b8e436b2cb30ba82e5590cb584ee.
Independent method publication:6c999edaaeec53ee10ca1bede97ab87e69ee7fb7; method tree:e5f5e4ec07e3569deb68692c6722218e7197f1f0.
Shipping source:5e2df5aaf23e9ed0e230c444a40650da9459ddb2.
Shipping executable SHA256:82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9.

One unmodified published test run on the current local Windows client. No physical targets, observer capture, VHD, elevation, security changes or retry.

| Case | Actual result |
|---|---|
| O1 owned file/process | Completed: exact file operations and two-stream exit7 child control |
| I0 CLI startup | Observed: no-args/help/version each returned exit2 and usage |
| I1 small image | Completed: provision/load/verify/dumpA+B; canonical outputs equal input; verify unchanged image |
| I2 overlength | Completed: exit2 with overage diagnostic; whole image unchanged |
| I3 wrong partition type | Completed: exit1/PARTITION_TYPE; whole bad image unchanged |
| Detecting controls | Eight FAT/date and three WAV-tail controls detected their defects |
| S1 sparse | Partial: high-offset marker rereads completed; allocation guard stopped before large-image CLI provision/verify |
| N1 observer | Ineligible: previously authenticated token lacks Administrator prerequisite |
| V0 VHD | Unavailable under published method |

Overall runner outcome: STOP, exit1, no timeout; inner elapsed57.031s. Prior capability/startup work plus this run remained under96seconds of new test wall. The allocation scope did not remain compliant: sparse logical length4296015872bytes, sparse attribute present, published allocation API reported4296015872bytes for that file and4298790617bytes for the runner root before stopping. No large-image shipping command ran. Sparse attribute is not evidence of bounded allocation. No budget reset or additional test followed.

Original receipts, per-command streams, ordinary inputs/outputs and complete file/runtime inventories remain in private local evidence under the existing owned Software534 area. The sparse file remains separate, without whole-file hashing or zero-hole transport expansion.

Original receipt SHA256:29c238596dcedc6b0591c8dacd8900bcc261ffc748c32a03906e8d5bedef488d.
Closed original-file inventory SHA256:3ed08b613c3b3285d5bdf67178bd8d66c8e806f7a820d1592ca4685b3525c87e.
Private runtime inventory SHA256:632c7c099bfd6189ee08dbf6ec92ef525a228c28e472036633dac5a150feaefa.
Source and canonical A/B output SHA256:b3b824e492523cb0b1b428b8a81a874707d3d978141386ce461f74c15dddb712.

Independent Verification277 owns disposition of completed rows, the sparse-method allocation finding and the remaining Windows CLI criterion ledger. Retained physical221/229 request/offset linkage remains held; no no-card surrogate supplies that missing physical relationship. No overall WP14 PASS, Product integration or new app scope is claimed.
