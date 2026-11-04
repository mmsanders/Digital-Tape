#!/usr/bin/env python3
"""Media atomicity — is a 512-byte SD block write atomic under power loss?

`spec/acceptance.md` DRAFT-4, via PM Decisions 004 section 1: across at least
1 000 cuts per SKU, every read must return either the previous content or the new
content in full, never a mixture. This is the single load-bearing physical
assumption under the format; `tapefs` section 8's commit protocol reduces to it.
A torn block is a BLOCKER and forces a format change, not a firmware workaround.

REVISION 3, after independent reviews IR-018 (rounds 1 and 2). Both rounds found
ways this tool could say PASS without the evidence to justify it. What changed:

  IR-018-06  The 1 000 minimum is now UNCONDITIONAL and lives in code, not in the
             plan file. `--cuts 0` used to produce a plan with zero trials and a
             threshold of zero, and an empty result set passed. Thresholds are no
             longer readable from operator-supplied input at all; tests inject a
             Policy object instead of going through the production file format.

  IR-018-07  A single DAT0-low sample is NOT proof of the programming phase. In
             native 4-bit mode DAT0 is a data line during the payload -- it can be
             low simply because the current bit is zero -- and the protocol's busy
             indication is a distinct phase AFTER the data-response token. In SPI
             mode busy is on MISO, not DAT0, and the bus mode was never stated.
             Qualification is now from protocol state: complete single-block
             payload, accepted data-response token, observed entry into the busy
             phase, and the busy indication still asserted when the rail opened.

  IR-018-08  Results are bound to card identity. SKU, revision and CID are
             required on every row and must match the plan exactly; `None` is no
             longer accepted. Rows are bound to a digest of the committed plan,
             and run ids are collision-resistant. The verdict reports identity
             only from cross-checked evidence, never by copying the plan.

  IR-018-09  Planned attempts and required qualifying cuts are separate numbers.
             Previously `--cuts N` set both, so a single correctly-identified
             non-qualifying attempt made PASS unreachable -- and since cut offsets
             deliberately span 0-1.5, misses are expected. A campaign now plans a
             surplus, and `plan --extend` issues an auditable continuation under
             the same run id when misses outrun it.

Every planned attempt must still be reported exactly once. Non-qualifying is a
result; missing is a broken run.

R374-1 (independent rig review, P3-R2-HW #651): qualification decides only what
counts toward the minimum. Every row that passes validation has its target and
neighbours classified whether or not it qualifies, so a tear on a late-cut row
can no longer disappear from a PASS. Imported regressions:
hardware/characterisation/verification/rig_correction_r2 (V380, bab04466).

Rig revision 2 (ATOMICITY-SCHEMA-R2, correction 1): qualifies() judges a row
that carries `method: "rig-r2"` from the measured rail-opening and busy-end
edges, with U and the cut-delay bound fixed in Policy. A plan-v4 run binds the
exact bytes of a rig manifest; load_manifest() hashes every evidence file it
names, and judge() cross-checks plan, rows and manifest. ADR-204: an otherwise
qualified completed write that reads back OLD fails run integrity
(completed_write_reverted). Imported regressions: verification/rig_timing_r1
(V382, 8879dbac) and verification/rig_records_r1 (45a6dda0). A rig-r2 row under
a plan-v3 run is refused.

    ./media_atomicity.py plan --sku S --revision R --cid C --attempts 1500 --out plan.json
    ./media_atomicity.py judge --plan plan.json [--plan ext.json] --results run.jsonl

  rig-r2 (plan v4) adds --manifest MANIFEST.json --evidence DIR to both.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import secrets
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BLOCK = 512
WORDS = BLOCK // 4
REQUIRED_QUALIFYING = 1000          # normative, from acceptance.md. Not negotiable.
DEFAULT_SURPLUS = 1.5               # plan this many attempts per required cut
NEIGHBOUR_OFFSETS = ("-2", "-1", "+1", "+2")
BUS_MODES = {"sd4": "DAT0", "spi": "MISO"}
METHOD_R2 = "rig-r2"                # ATOMICITY-SCHEMA-R2 section 2


@dataclass(frozen=True)
class Policy:
    """Acceptance thresholds. Injected, never read from operator input.

    IR-018-06: the production minimum is a property of the criterion, not of a
    file the operator writes. Tests construct their own Policy; the CLI cannot.
    The rig-r2 timing constants are the same kind of thing: a row field called
    U_US or CUT_DELAY_MAX_US is ignored.
    """
    min_qualifying: int = REQUIRED_QUALIFYING
    u_us: float = 1.0                # edge-alignment uncertainty U (model value)
    cut_delay_max_us: float = 500.0  # cut command to measured rail opening
    a_fall_v: tuple = (2.570, 2.610) # control E0 window, comparator A falling
    b_rise_v: tuple = (1.010, 1.040) # control E0 window, comparator B rising
    skew_max_ns: float = 300.0       # control E3 limit
    skew_min_edges: int = 1000


PRODUCTION = Policy()


def pattern(n: int) -> bytes:
    return struct.pack("<I", n & 0xFFFFFFFF) * WORDS


def classify(data: bytes, n: int) -> str:
    if len(data) != BLOCK:
        return "CORRUPT"
    words = set(struct.unpack("<%dI" % WORDS, data))
    old, new = (n - 1) & 0xFFFFFFFF, n & 0xFFFFFFFF
    if words == {old}:
        return "OLD"
    if words == {new}:
        return "NEW"
    if words <= {old, new}:
        return "TORN"
    return "CORRUPT"


def plan_digest(plan: dict) -> str:
    """Digest over identity and schedule, so results cannot be re-pointed.

    A plan-v4 digest also covers the method and the manifest hash, so a run
    can't be moved to another rig build or calibration (schema R2 section 3).
    """
    core = {k: plan[k] for k in ("run_id", "sku", "revision", "card_cid", "block",
                                 "neighbour_offsets", "method", "rig_manifest_sha256")
            if k in plan}
    core["trials"] = [[t["iteration"], t["cut_offset_fraction"]] for t in plan["trials"]]
    return hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def strict_loads(text: str):
    """JSON with no NaN, Infinity or duplicate keys (schema R2 section 5.1)."""
    def pairs(kv):
        d = {}
        for k, v in kv:
            if k in d:
                raise ValueError(f"duplicate key {k!r}")
            d[k] = v
        return d

    def constant(name):
        raise ValueError(f"non-finite number {name}")

    def finite(s):
        v = float(s)
        if not math.isfinite(v):
            raise ValueError(f"non-finite number {s}")
        return v

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant,
                      parse_float=finite)


# --------------------------------------------------------------------------
# rig manifest (schema R2 section 5)
# --------------------------------------------------------------------------

CONTROLS = ("E0", "E1", "E2", "E3", "E4", "A", "B", "B2", "C", "D", "E", "F", "G")
RIG_DOC = "hardware/characterisation/ATOMICITY-RIG.md"


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _is_hex(v, n: int) -> bool:
    return isinstance(v, str) and len(v) == n and all(c in "0123456789abcdef" for c in v)


def _num(v) -> bool:
    """A finite JSON number. Never raises: math.isfinite overflows on a huge int,
    and every int is finite, so ints skip it (HW651-R2)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return isinstance(v, int) or math.isfinite(v)


def _pos_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _text(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


class _Manifest:
    """Collects every problem in one pass; never raises on bad input."""

    def __init__(self, evidence: Path):
        self.evidence = evidence
        self.problems: list[str] = []

    def bad(self, where: str, why: str) -> None:
        self.problems.append(f"{where}: {why}")

    def obj(self, v, keys, where: str) -> bool:
        if not isinstance(v, dict):
            self.bad(where, "not an object")
            return False
        if set(v) != set(keys):
            self.bad(where, f"keys must be exactly {sorted(keys)}")
            return False
        return True

    def check(self, where: str, ok: bool, why: str) -> None:
        if not ok:
            self.bad(where, why)

    def ref(self, v, where: str) -> None:
        """A ref names evidence bytes; the bytes are read and hashed, not trusted."""
        if not self.obj(v, ("path", "sha256"), where):
            return
        p, h = v["path"], v["sha256"]
        if not _is_hex(h, 64):
            return self.bad(where, "sha256 is not 64 lowercase hex")
        if (not isinstance(p, str) or not p or "\\" in p or "\0" in p
                or p.startswith("/") or ":" in p
                or any(part in ("", ".", "..") for part in p.split("/"))):
            return self.bad(where, f"path {p!r} is not a relative path inside the evidence")
        f = self.evidence / p
        try:
            if self.evidence.resolve() not in f.resolve().parents:
                return self.bad(where, f"path {p!r} leaves the evidence directory")
            data = f.read_bytes()
        except (OSError, ValueError):
            return self.bad(where, f"evidence file {p!r} is missing or unreadable")
        if _sha256(data) != h:
            self.bad(where, f"evidence file {p} does not match its sha256")

    def window(self, v, where: str, lo: float, hi: float) -> None:
        if not (isinstance(v, list) and len(v) == 5 and all(_num(x) for x in v)):
            return self.bad(where, "must be a list of 5 numbers")
        if not all(lo <= x <= hi for x in v):
            self.bad(where, f"a measurement is outside {lo}-{hi}")


def load_manifest(path, evidence_dir, policy: Policy = PRODUCTION):
    """Read, hash, parse and authenticate a rig manifest (schema R2 section 5.3).

    Returns (manifest, sha256 of its exact bytes, problems). An empty problem list
    is the only success. What it can't establish: that a certificate is genuine,
    that a measurement was taken as described, or which binary actually ran.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as e:
        return None, None, [f"manifest {path} cannot be read: {e.strerror}"]
    digest = _sha256(raw)
    try:
        m = strict_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        return None, digest, [f"manifest is not strict UTF-8 JSON: {e}"]
    c = _Manifest(Path(evidence_dir))
    try:
        _check_manifest(m, c, policy)
    except Exception as e:
        # HW651-R2 backstop: the contract is problems, never an exception. Any
        # problem refuses the manifest, so this can only fail closed.
        c.bad("manifest", f"check stopped on bad input ({type(e).__name__})")
    return (m if isinstance(m, dict) else None), digest, c.problems


def _check_manifest(m, c: _Manifest, policy: Policy) -> None:
    """The grammar of schema R2 section 5.3. Every finding goes to c.problems."""
    if not c.obj(m, ("method", "rig_doc", "firmware", "host_script", "judge_sha256", "bus",
                     "capture", "switch", "thresholds_measured", "skew_measured_ns",
                     "controls", "card"), "manifest"):
        return

    c.check("method", m["method"] == METHOD_R2, f"must be {METHOD_R2!r}")
    if c.obj(m["rig_doc"], ("path", "git_blob"), "rig_doc"):
        c.check("rig_doc.path", m["rig_doc"]["path"] == RIG_DOC, f"must be {RIG_DOC}")
        c.check("rig_doc.git_blob", _is_hex(m["rig_doc"]["git_blob"], 40), "not 40 hex")
    if c.obj(m["firmware"], ("source_commit", "binary"), "firmware"):
        c.check("firmware.source_commit", _is_hex(m["firmware"]["source_commit"], 40), "not 40 hex")
        c.ref(m["firmware"]["binary"], "firmware.binary")
    c.ref(m["host_script"], "host_script")
    c.check("judge_sha256", m["judge_sha256"] == _sha256(Path(__file__).read_bytes()),
            "is not the SHA-256 of this judge")

    if c.obj(m["bus"], ("mode", "busy_line", "sck_hz"), "bus"):
        c.check("bus.mode", m["bus"]["mode"] == "spi", "this rig is SPI only")
        c.check("bus.busy_line", m["bus"]["busy_line"] == "MISO", "must be MISO")
        c.check("bus.sck_hz", _pos_int(m["bus"]["sck_hz"]), "not a positive integer")
    if c.obj(m["capture"], ("timer", "clock_hz", "pin_a", "pin_b"), "capture"):
        cap = m["capture"]
        c.check("capture.timer", _text(cap["timer"]), "empty")
        c.check("capture.clock_hz", _pos_int(cap["clock_hz"]), "not a positive integer")
        for k in ("pin_a", "pin_b"):
            c.check(f"capture.{k}", isinstance(cap[k], int) and not isinstance(cap[k], bool)
                    and cap[k] >= 0, "not a pin number")
    fixed = {"revision": "r2", "part": "TPS22918", "buffer_part": "SN74LVC1G125",
             "comparator_part": "TLV3202"}
    values = ("ct_nf", "r_ext_ohm", "bulk_uf", "hysteresis_ohm")
    if c.obj(m["switch"], tuple(fixed) + values, "switch"):
        for k, want in fixed.items():
            c.check(f"switch.{k}", m["switch"][k] == want, f"must be {want!r}")
        for k in values:
            c.check(f"switch.{k}", _num(m["switch"][k]) and m["switch"][k] > 0,
                    "not a positive number")

    t = m["thresholds_measured"]
    if c.obj(t, ("a_falling_v", "b_rising_v", "instrument", "raw"), "thresholds_measured"):
        c.window(t["a_falling_v"], "thresholds_measured.a_falling_v", *policy.a_fall_v)
        c.window(t["b_rising_v"], "thresholds_measured.b_rising_v", *policy.b_rise_v)
        if c.obj(t["instrument"], ("model", "serial", "calibration"), "instrument"):
            c.check("instrument.model", _text(t["instrument"]["model"]), "empty")
            c.check("instrument.serial", _text(t["instrument"]["serial"]), "empty")
            c.ref(t["instrument"]["calibration"], "instrument.calibration")
        c.ref(t["raw"], "thresholds_measured.raw")
    s = m["skew_measured_ns"]
    if c.obj(s, ("max_abs", "edges", "raw"), "skew_measured_ns"):
        c.check("skew_measured_ns.max_abs", _num(s["max_abs"])
                and 0 <= s["max_abs"] <= policy.skew_max_ns, f"not within 0-{policy.skew_max_ns} ns")
        c.check("skew_measured_ns.edges", isinstance(s["edges"], int)
                and not isinstance(s["edges"], bool) and s["edges"] >= policy.skew_min_edges,
                f"fewer than {policy.skew_min_edges} edges")
        c.ref(s["raw"], "skew_measured_ns.raw")

    if c.obj(m["controls"], CONTROLS, "controls"):
        for k in CONTROLS:
            ctl, where = m["controls"][k], f"controls.{k}"
            if not c.obj(ctl, ("result", "date", "witness", "evidence"), where):
                continue
            # A recorded failure stays as evidence, and refuses the run.
            c.check(where, ctl["result"] == "pass", f"result is {ctl['result']!r}, not 'pass'")
            d = ctl["date"]
            c.check(f"{where}.date", isinstance(d, str) and len(d) == 10 and d[4] == d[7] == "-"
                    and (d[:4] + d[5:7] + d[8:]).isdigit(), "not YYYY-MM-DD")
            c.check(f"{where}.witness", _text(ctl["witness"]), "empty")
            ev = ctl["evidence"]
            if not isinstance(ev, list) or not ev:
                c.bad(f"{where}.evidence", "needs at least one ref")
            else:
                for i, r in enumerate(ev):
                    c.ref(r, f"{where}.evidence[{i}]")

    card = m["card"]
    if c.obj(card, ("mpn", "mpn_photo", "retail_name", "capacity_bytes", "cid", "decoded",
                    "revision"), "card"):
        for k in ("mpn", "retail_name", "revision"):
            c.check(f"card.{k}", _text(card[k]), "empty")
        c.ref(card["mpn_photo"], "card.mpn_photo")
        c.check("card.capacity_bytes", _pos_int(card["capacity_bytes"]), "not a positive integer")
        c.check("card.cid", _is_hex(card["cid"], 32), "not 32 lowercase hex")
        if c.obj(card["decoded"], ("mid", "oid", "pnm", "prv", "psn", "mdt"), "card.decoded"):
            for k, v in card["decoded"].items():
                c.check(f"card.decoded.{k}", isinstance(v, (int, str)) and not isinstance(v, bool),
                        "not a string or integer")


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def cmd_plan(a) -> int:
    prior = strict_loads(Path(a.extend).read_text(encoding="utf-8")) if a.extend else None
    rig_r2 = bool(a.manifest) or (prior is not None and prior.get("plan_version") == 4)
    if rig_r2:
        # Schema R2 section 3: a v4 plan binds the exact manifest bytes, and a
        # continuation re-authenticates the same bytes rather than trusting them.
        if not (a.manifest and a.evidence):
            sys.exit("plan: a rig-r2 plan needs --manifest and --evidence")
        if prior is not None and prior.get("plan_version") != 4:
            sys.exit("plan: a revision-3 plan can't be continued with a rig manifest")
        m, msha, mprob = load_manifest(a.manifest, a.evidence)
        if mprob:
            sys.exit("plan: the rig manifest is not valid:\n  " + "\n  ".join(mprob))
        if prior is not None and (prior.get("method") != METHOD_R2
                                  or prior.get("rig_manifest_sha256") != msha):
            sys.exit("plan: the manifest bytes differ from the plan being extended; "
                     "a different manifest needs a new run")
    if prior:
        run_id, sku, rev, cid = (prior["run_id"], prior["sku"],
                                 prior["revision"], prior["card_cid"])
        start = max(t["iteration"] for t in prior["trials"]) + 1
        block = prior["block"]
    else:
        if not (a.sku and a.revision and a.cid):
            sys.exit("plan: --sku, --revision and --cid are all required "
                     "(IR-018-08: results are bound to card identity)")
        run_id = f"{a.sku.replace(' ', '-')}-{a.revision}-{secrets.token_hex(8)}"
        sku, rev, cid = a.sku, a.revision, a.cid
        start, block = 1, a.block

    # `a.attempts or default` would silently turn an explicit 0 into the default.
    # An out-of-range request must be refused, not quietly corrected.
    attempts = (int(REQUIRED_QUALIFYING * DEFAULT_SURPLUS)
                if a.attempts is None else a.attempts)
    if not prior and attempts < REQUIRED_QUALIFYING:
        sys.exit(f"plan: --attempts must be at least {REQUIRED_QUALIFYING}; "
                 f"the criterion needs that many QUALIFYING cuts and misses are "
                 f"expected, so plan a surplus (default "
                 f"{int(REQUIRED_QUALIFYING * DEFAULT_SURPLUS)})")
    if rig_r2 and (sku, rev, cid) != (m["card"]["mpn"], m["card"]["revision"], m["card"]["cid"]):
        sys.exit("plan: --sku, --revision and --cid must equal the manifest's card "
                 "mpn, revision and cid")

    rng = random.Random(a.seed)
    plan = {
        "plan_version": 3,
        "run_id": run_id, "sku": sku, "revision": rev, "card_cid": cid,
        "block": block,
        "neighbour_offsets": list(NEIGHBOUR_OFFSETS),
        "planned_attempts": attempts,
        "required_qualifying": REQUIRED_QUALIFYING,
        "note": ("required_qualifying is informational. The judge enforces its own "
                 "minimum and ignores this field (IR-018-06)."),
        "extends": prior["run_id"] if prior else None,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trials": [{"iteration": n, "cut_offset_fraction": round(rng.random() * 1.5, 4)}
                   for n in range(start, start + attempts)],
    }
    if rig_r2:
        plan.update(plan_version=4, method=METHOD_R2, rig_manifest_sha256=msha)
    plan["plan_digest"] = plan_digest(plan)
    out = json.dumps(plan, indent=2) + "\n"
    if a.out:
        Path(a.out).write_text(out)
        print(f"wrote {a.out}")
        print(f"  run_id  {run_id}")
        print(f"  trials  {attempts} attempts, iterations "
              f"{start}..{start + attempts - 1}")
        print(f"  judge requires {REQUIRED_QUALIFYING} QUALIFYING cuts; the surplus "
              f"absorbs expected misses")
    else:
        print(out)
    return 0


# --------------------------------------------------------------------------
# judge
# --------------------------------------------------------------------------

def _hex(v, n=BLOCK):
    if not isinstance(v, str):
        return None
    try:
        b = bytes.fromhex(v)
    except ValueError:
        return None
    return b if len(b) == n else None


def validate_trial(r: dict, n: int, plan: dict, manifest: dict | None = None) -> tuple[bool, str]:
    if r.get("iteration") != n:
        return False, f"iteration mismatch: {r.get('iteration')} != {n}"
    # Schema R2: a rig-r2 row earns credit only under a plan-v4 run with an
    # authenticated manifest, never through a revision-3 plan.
    v4 = plan.get("plan_version") == 4
    if "method" in r and not v4:
        return False, "rig-r2 rows need a plan-v4 run with a rig manifest"

    # IR-018-08: identity on every row, exact, no None.
    for field in ("sku", "revision", "card_cid"):
        if not r.get(field):
            return False, f"{field} missing"
        if r[field] != plan[field]:
            return False, f"{field} does not match the plan"
    if r.get("plan_digest") != plan["plan_digest"]:
        return False, "plan_digest does not match the committed plan"

    # IR-018-04: the old image is established, not inferred.
    if r.get("precondition_ok") is not True:
        return False, "precondition_ok is not true"
    if _hex(r.get("precondition_readback_hex")) != pattern(n - 1):
        return False, "precondition readback is not exactly pattern N-1"

    if _hex(r.get("readback_hex")) is None:
        return False, "readback missing or not 512 bytes"

    # IR-018-03: all four offsets, each with its own baseline.
    nb, base = r.get("neighbours"), r.get("neighbour_baseline")
    if not isinstance(nb, dict) or not isinstance(base, dict):
        return False, "neighbours/neighbour_baseline missing"
    if set(nb) != set(NEIGHBOUR_OFFSETS) or set(base) != set(NEIGHBOUR_OFFSETS):
        return False, f"neighbour offsets must be exactly {list(NEIGHBOUR_OFFSETS)}"
    for off in NEIGHBOUR_OFFSETS:
        if _hex(nb[off]) is None or _hex(base[off]) is None:
            return False, f"neighbour {off} missing or not 512 bytes"
    return _validate_r2(r, plan, manifest) if v4 else (True, "")


def _validate_r2(r: dict, plan: dict, manifest: dict | None) -> tuple[bool, str]:
    """Schema R2 section 4.1: rig-r2 row validation. Failure is a run problem."""
    if r.get("method") != METHOD_R2 or plan.get("method") != METHOD_R2:
        return False, f"method is not {METHOD_R2!r} on both row and plan"
    if r.get("rig_manifest_sha256") != plan.get("rig_manifest_sha256"):
        return False, "rig_manifest_sha256 does not match the plan"
    if not _is_hex(r.get("card_cid_after_cut"), 32):
        return False, "card_cid_after_cut missing or malformed"
    if r["card_cid_after_cut"] != r["card_cid"]:
        return False, "CID after cut differs"
    if r.get("rail_high_at_arm") is not True:
        return False, "rail_high_at_arm is not true"
    # A recorder that writes contradictions can't be trusted on its other rows.
    bad = _r2_record(r)
    if bad:
        return False, f"rig-r2 record invalid: {bad}"
    if manifest is None:            # already a run problem; nothing to compare with
        return True, ""
    want = {"bus_mode": manifest["bus"]["mode"], "busy_line": manifest["bus"]["busy_line"],
            "sck_hz": manifest["bus"]["sck_hz"], "card_cid": manifest["card"]["cid"],
            "firmware_source_commit": manifest["firmware"]["source_commit"],
            "switch_revision": manifest["switch"]["revision"]}
    for k, v in want.items():
        if r.get(k) != v or isinstance(r.get(k), bool):
            return False, f"{k} does not match the rig manifest"
    return True, ""


def _time(v) -> bool:
    """A rig-r2 time: a finite real number >= 0. A bool is not a number."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v >= 0)


def _r2_record(r: dict) -> str:
    """Schema R2 section 4.3: why the timing record contradicts itself, or ''."""
    scalars = ("capture_armed_us", "busy_entry_us", "cut_command_us", "capture_end_us")
    lists = ("rail_edges_us", "busy_end_edges_us")
    for k in scalars + lists + ("rail_open_us",):
        if k not in r:
            return f"{k} missing"                                        # R1
    for k in scalars:
        if not _time(r[k]):
            return f"{k} is not a finite time >= 0"                      # R2
    ro = r["rail_open_us"]
    if ro is not None and not _time(ro):
        return "rail_open_us is not a finite time >= 0 or null"
    for k in lists:                                                      # R3
        v = r[k]
        if not isinstance(v, list) or not all(_time(e) for e in v):
            return f"{k} is not a list of finite times >= 0"
        if any(b <= a for a, b in zip(v, v[1:])):
            return f"{k} is not strictly increasing"
    lo, hi = r["capture_armed_us"], r["capture_end_us"]
    if lo > hi:                                                          # R4
        return "capture ended before it was armed"
    for k in lists:                                                      # R5
        if any(not lo <= e <= hi for e in r[k]):
            return f"{k} has an edge outside the capture window"
    edges = r["rail_edges_us"]                                           # R6
    if (ro is None) != (not edges) or (edges and ro != edges[0]):
        return "rail_open_us is not the first recorded rail edge"
    if r.get("rail_high_at_arm", True) is not True:                      # R7
        return "rail was not high when capture was armed"
    return ""


SETUP_UNPROVEN = "rig setup not authenticated"
R2_COMPLETED_BEFORE = "busy ended before the rail opened"


def completion_proven(r: dict, reason: str) -> bool:
    """ADR-204: an otherwise qualified row whose busy ended strictly before rail_open - U.

    The completed-before check runs before the chatter check in _qualifies_r2,
    so that first-failure reason alone isn't proof: chatter is excluded here too.
    Every earlier check (protocol, record, arming, opening, delay, window) has
    already passed whenever this reason is returned.
    """
    return (r.get("method") == METHOD_R2 and reason == R2_COMPLETED_BEFORE
            and len(r["rail_edges_us"]) == 1)


def _qualifies_r2(r: dict, policy: Policy) -> tuple[bool, str]:
    """Schema R2 section 4.4: qualify from the measured A and B edges.

    R374-2: no software timestamp stands in for an electrical event. ADR-204:
    completed-before is strictly busy_end < rail_open - U, and equality at
    either boundary is ambiguous, so it can never become completion proof.
    """
    bad = _r2_record(r)
    if bad:
        return False, f"rig-r2 record invalid: {bad}"
    u = policy.u_us
    entry, ro = r["busy_entry_us"], r["rail_open_us"]
    if r["capture_armed_us"] > entry:
        return False, "busy capture not armed at busy entry"
    if ro is None or ro <= entry:
        return False, "rail opening not observed after busy entry"
    if not 0 <= ro - r["cut_command_us"] <= policy.cut_delay_max_us:
        return False, "rail opening outside the cut delay bound"
    if r["capture_end_us"] < ro + u:
        return False, "capture did not cover the uncertainty window"
    ends = [e for e in r["busy_end_edges_us"] if e >= entry]
    if any(e < ro - u for e in ends):
        return False, R2_COMPLETED_BEFORE
    if any(e <= ro + u for e in ends):
        return False, "busy end within +/-U of rail opening (ambiguous)"
    if len(r["rail_edges_us"]) != 1:
        return False, "rail chatter after opening"
    return True, ""


def qualifies(r: dict, policy: Policy = PRODUCTION) -> tuple[bool, str]:
    """IR-018-07: qualify from protocol state, not from a pin level.

    A DAT0-low sample proves nothing on its own. In 4-bit mode DAT0 carries data
    during the payload and is low whenever the current bit is zero; the busy
    indication is a distinct phase entered only after the data-response token is
    accepted. In SPI mode the indication is on MISO instead. So a trial qualifies
    only if the rig can show the whole sequence: payload transferred, response
    token accepted, busy phase entered, and busy still asserted when the rail
    opened.
    """
    bus = r.get("bus_mode")
    if bus not in BUS_MODES:
        return False, f"bus_mode must be one of {sorted(BUS_MODES)}"
    if r.get("busy_line") != BUS_MODES[bus]:
        return False, f"busy_line for {bus} must be {BUS_MODES[bus]}"
    if r.get("payload_complete") is not True:
        return False, "single-block payload not proven complete"
    if r.get("data_response_accepted") is not True:
        return False, "data-response token not accepted"

    if "method" in r:
        if r["method"] != METHOD_R2:
            return False, f"method must be {METHOD_R2!r}"
        return _qualifies_r2(r, policy)

    be, bs, cut = (r.get("busy_entry_us"), r.get("busy_sampled_us"), r.get("cut_us"))
    if not all(isinstance(v, (int, float)) for v in (be, bs, cut)):
        return False, "busy_entry_us / busy_sampled_us / cut_us missing"
    if not (be <= bs <= cut):
        return False, "busy was not observed asserted before the rail opened"
    de = r.get("busy_deassert_us")
    if isinstance(de, (int, float)) and de <= cut:
        return False, "busy ended before the cut -- the write had completed"
    return True, ""


def judge(plans: list[dict], rows: list[dict], policy: Policy = PRODUCTION,
          manifest: tuple | None = None) -> dict:
    """`manifest` is load_manifest()'s result; a plan-v4 run needs one."""
    problems: list[str] = []

    head = plans[0]
    for p in plans[1:]:
        if p["run_id"] != head["run_id"] and p.get("extends") != head["run_id"]:
            problems.append(f"plan {p['run_id']} is not a continuation of {head['run_id']}")
    for p in plans:
        if plan_digest(p) != p.get("plan_digest"):
            problems.append(f"plan {p.get('run_id')}: digest does not match its contents")

    # Schema R2 section 5.3: authenticate the manifest the plan binds.
    v4 = head.get("plan_version") == 4
    mf = None
    if v4:
        for p in plans:
            if (p.get("plan_version"), p.get("method"), p.get("rig_manifest_sha256")) != (
                    4, METHOD_R2, head.get("rig_manifest_sha256")):
                problems.append(f"plan {p.get('run_id')}: not a plan-v4 {METHOD_R2} plan "
                                f"for the same manifest")
        if manifest is None:
            problems.append("a plan-v4 run needs a loaded rig manifest")
        else:
            m, msha, mprob = manifest
            problems.extend(f"rig manifest: {x}" for x in mprob)
            if msha != head.get("rig_manifest_sha256"):
                problems.append("rig manifest bytes are not the ones the plan binds")
            elif not mprob and isinstance(m, dict):
                mf = m
                card = (m["card"]["mpn"], m["card"]["revision"], m["card"]["cid"])
                if card != (head.get("sku"), head.get("revision"), head.get("card_cid")):
                    problems.append("plan sku/revision/card_cid do not match the manifest's card")
                    mf = None

    # HW651-R1 / ADR-204: a plan-v4 row earns qualifying credit or completion
    # proof only against an authenticated manifest whose card matches the plan.
    # Without one, rows are still validated, classified and reported as damage.
    unproven = v4 and mf is None

    trials: dict[int, dict] = {}
    for p in plans:
        for t in p["trials"]:
            trials[t["iteration"]] = p
    expected = set(trials)
    planned_attempts = len(expected)

    # IR-018-02 / IR-018-08
    seen: dict[int, dict] = {}
    for r in rows:
        n = r.get("iteration")
        p = trials.get(n)
        if p is None:
            problems.append(f"trial {n}: not in any committed plan")
            continue
        if r.get("run_id") != p["run_id"]:
            problems.append(f"trial {n}: run_id mismatch")
            continue
        if n in seen:
            problems.append(f"trial {n}: duplicate result")
            continue
        seen[n] = r
    for n in sorted(expected - set(seen)):
        problems.append(f"trial {n}: planned but not reported")

    verdicts, tears, corrupt, neigh_bad = Counter(), [], [], []
    verdicts_nq: Counter = Counter()
    damage_nq: list = []
    qualifying = 0
    non_qualifying: Counter = Counter()
    identity: set[tuple] = set()
    reverted: list[int] = []
    bus_seen: set = set()
    sck_seen: set = set()

    for n in sorted(seen):
        r, p = seen[n], trials[n]
        ok, why = validate_trial(r, n, p, mf)
        if not ok:
            problems.append(f"trial {n}: {why}")
            continue
        identity.add((r["sku"], r["revision"], r["card_cid"]))
        bus_seen.add(r.get("bus_mode"))
        sck_seen.add(r.get("sck_hz"))
        q, why = qualifies(r, policy)
        if unproven:
            q, why = False, SETUP_UNPROVEN
        if q:
            qualifying += 1
        else:
            non_qualifying[why] += 1
        # R374-1: a miss earns no credit, but its returned data is still audited.
        v = classify(bytes.fromhex(r["readback_hex"]), n)
        (verdicts if q else verdicts_nq)[v] += 1
        # ADR-204: proven completion that reads back OLD fails run integrity.
        # No credit, and it's not relabelled TORN or called a media defect.
        if v4 and v == "OLD" and completion_proven(r, why):
            reverted.append(n)
            problems.append(f"trial {n}: completed_write_reverted (busy ended before "
                            f"rail_open - U, target reads OLD)")
        damaged = False
        if v == "TORN":
            tears.append(n)
            damaged = True
        elif v == "CORRUPT":
            corrupt.append(n)
            damaged = True
        for off in NEIGHBOUR_OFFSETS:
            if bytes.fromhex(r["neighbours"][off]) != bytes.fromhex(r["neighbour_baseline"][off]):
                neigh_bad.append([n, off])
                damaged = True
        if damaged and not q:
            damage_nq.append(n)

    if len(identity) > 1:
        problems.append(f"results span {len(identity)} distinct cards; expected one")
    if v4 and (len(bus_seen) > 1 or len(sck_seen) > 1):
        problems.append("results span more than one bus mode or SCK")

    ok = (not problems and not tears and not corrupt and not neigh_bad and not reverted
          and qualifying >= policy.min_qualifying and len(identity) == 1)

    # IR-018-08: identity from evidence, never copied from the plan.
    sku, revision, cid = (sorted(identity)[0] if len(identity) == 1
                          else (None, None, None))
    bus = sorted(bus_seen, key=str)[0] if len(bus_seen) == 1 else None
    return {
        "run_id": head["run_id"],
        "method": head.get("method"),
        "rig_manifest_sha256": head.get("rig_manifest_sha256"),
        "bus_mode": bus,
        "sck_hz": sorted(sck_seen, key=str)[0] if len(sck_seen) == 1 else None,
        # R374-5: SPI is characterisation, never SD 4-bit or card qualification.
        "qualification_scope": {"spi": "spi-characterisation", "sd4": "sd4"}.get(bus),
        "completed_write_reverted": reverted,
        "sku": sku, "revision": revision, "card_cid": cid,
        "planned_attempts": planned_attempts, "reported": len(seen),
        "qualifying": qualifying, "required_qualifying": policy.min_qualifying,
        "non_qualifying": dict(non_qualifying),
        "verdicts": dict(verdicts),
        "verdicts_non_qualifying": dict(verdicts_nq),
        "damage_on_non_qualifying": damage_nq,
        "torn_iterations": tears, "corrupt_iterations": corrupt,
        "neighbour_damage": neigh_bad,
        "problems": problems,
        "verdict": "PASS" if ok else "FAIL",
        "judged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def cmd_judge(a) -> int:
    try:
        plans = [strict_loads(Path(p).read_text(encoding="utf-8")) for p in a.plan]
        rows = [strict_loads(l) for l in Path(a.results).read_text(encoding="utf-8").splitlines()
                if l.strip()]
    except (UnicodeDecodeError, ValueError) as e:
        print(f"judge: refused, not strict JSON: {e}", file=sys.stderr)
        return 2
    manifest = None
    if a.manifest or a.evidence:
        if not (a.manifest and a.evidence):
            print("judge: --manifest and --evidence go together", file=sys.stderr)
            return 2
        manifest = load_manifest(a.manifest, a.evidence)
    res = judge(plans, rows, manifest=manifest)   # production policy, always

    print(f"run        {res['run_id']}")
    if res["method"]:
        print(f"method     {res['method']}  manifest {res['rig_manifest_sha256']}")
        print(f"bus        {res['bus_mode']}  SCK {res['sck_hz']}  "
              f"scope {res['qualification_scope']}")
    print(f"card       {res['sku']}  rev {res['revision']}  CID {res['card_cid']}")
    print(f"attempts   {res['planned_attempts']} planned, {res['reported']} reported")
    print(f"QUALIFYING {res['qualifying']}   (criterion needs >= {res['required_qualifying']})")
    for why, k in sorted(res["non_qualifying"].items(), key=lambda kv: -kv[1]):
        print(f"  not counted: {k:>6}  {why}")
    for k in ("OLD", "NEW", "TORN", "CORRUPT"):
        print(f"  {k:<8} {res['verdicts'].get(k, 0):>6}")
    if res["verdicts_non_qualifying"]:
        print("  not counted, still audited: " + ", ".join(
            f"{k} {res['verdicts_non_qualifying'].get(k, 0)}"
            for k in ("OLD", "NEW", "TORN", "CORRUPT")))
    print(f"neighbour damage: {len(res['neighbour_damage'])}")
    if res["damage_on_non_qualifying"]:
        print(f"  damage on non-qualifying trials: {res['damage_on_non_qualifying'][:8]}")
    if res["problems"]:
        print(f"run integrity problems: {len(res['problems'])}")
        for p in res["problems"][:8]:
            print(f"  - {p}")
        if len(res["problems"]) > 8:
            print(f"  ... and {len(res['problems']) - 8} more")
    print(f"\nVERDICT    {res['verdict']}")
    if res["torn_iterations"]:
        print("  *** TORN blocks. BLOCKER: this forces a format change, not a")
        print("  *** firmware workaround.")
    if res["neighbour_damage"]:
        print("  *** Neighbour-block corruption: the FTL damaged data nobody wrote.")
    if res["completed_write_reverted"]:
        print(f"  *** completed_write_reverted {res['completed_write_reverted'][:8]}: busy ended")
        print("  *** before the rail opened, yet the target reads OLD. Review the traces")
        print("  *** before calling it card behaviour; comparator A's lag can over-report.")
    if res["qualifying"] < res["required_qualifying"]:
        short = res["required_qualifying"] - res["qualifying"]
        print(f"  {short} short of the required qualifying cuts. Issue a continuation")
        print(f"  with `plan --extend` rather than editing this run.")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(res, indent=2) + "\n")
        print(f"\nwrote {a.json}")
    return 0 if res["verdict"] == "PASS" else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="emit a committed cut schedule")
    p.add_argument("--sku"); p.add_argument("--revision"); p.add_argument("--cid")
    p.add_argument("--attempts", type=int,
                   help=f"planned attempts (default {int(REQUIRED_QUALIFYING * DEFAULT_SURPLUS)}); "
                        f"the judge always requires {REQUIRED_QUALIFYING} qualifying")
    p.add_argument("--extend", help="prior plan to continue under the same run id")
    p.add_argument("--block", type=int, default=1_000_000)
    p.add_argument("--seed", type=int, default=20260903)
    p.add_argument("--manifest", help="rig-r2 manifest; makes a plan-v4 run")
    p.add_argument("--evidence", help="directory holding the manifest's evidence files")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_plan)

    j = sub.add_parser("judge", help="classify a run against its committed plan(s)")
    j.add_argument("--plan", action="append", required=True,
                   help="repeat for continuation plans")
    j.add_argument("--results", required=True)
    j.add_argument("--manifest", help="rig-r2 manifest (required for a plan-v4 run)")
    j.add_argument("--evidence", help="directory holding the manifest's evidence files")
    j.add_argument("--json")
    j.set_defaults(fn=cmd_judge)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
