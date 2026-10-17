# Retained Windows 11 capture, after V146-WIN-R3-01/02 (Software #439)

Software's replay, not acceptance. Input: Michael's original ZIP from release
`wp14-a6-win-rehearsal` (98,602,972 bytes, SHA-256
`9b23466b502f386bc3c12ac8a6674710d0caf9491358c2c654bb5717d7cbd755`); every used member
checked against Verification's pins by `retained-win11.py`.

| File | What |
|---|---|
| `result.json` | `retained-win11.py` on the full 1,232,801-event export with this head's `a6check.py` |
| `verification-controls-r3.json` | Verification's 16 controls (`findings/P2-R1-WP14-A6-R3-2026-10-16/controls.py`, SHA-256 `17b12a38…192f`, run unchanged from their publication) against this head's checker |
| `selftest.txt` | `selftest.py` with `TAPECTL` = released tapectl-linux `4d8c97a4…`: 199 cases, 0 unexpected |

Earlier results (`../win11-retained-2026-10-16/`, `../win11-retained-2026-10-16-r2/`) are kept unchanged.
