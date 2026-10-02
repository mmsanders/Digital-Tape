#!/usr/bin/env python3
"""Independent oracle for the DRAFT-10 residue-destination rows (Verification #138, V10-001).

Every observation is checked twice:

1. Exactly, against the model. The trace is the planned tapefs §9.5/§9.6 order. The durable image
   is one a conforming §8.1 device may hold at that injection, and the mount result is what §4.1
   gives for those bytes.
2. Against the issued crash tables, by phase: residue zeroing and steps 2–3 must be unmountable; the
   fresh mirror write may be unmountable or the completed operation; from the fresh primary write
   onward only the completed operation is allowed. On top of that, the absolute WP-10 identity
   property: no injection may mount under any identity other than the fresh one.

With `outcome_only=True`, only the absolute property and the row-level result sets are checked.
That is the causal-control mode showing that a defect is visible from outcomes alone, without
trusting the trace.
"""
from __future__ import annotations

import json

import plan as P
from pins import M

SCHEMA = "wp10-residue-d10-observation-v1"
UNM = {"TAPE_ERR_BAD_MAGIC", "TAPE_ERR_CRC"}
PERMIT = {"residue": {"unmountable"}, "steps23": {"unmountable"}, "sb_mirror": {"unmountable", "completed"},
          "sb_primary": {"completed"}, "after": {"completed"}}
CALL = {"dup": "tape_dup", "format": "tape_format"}
FORBIDDEN_KEYS = {"verdict", "passed", "permitted", "expected", "outcome_ok", "row_ok", "phase", "category"}
SB_LBAS = {M.TRACKED["P"], M.TRACKED["M"]}


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")


class Oracle:
    def __init__(self):
        self.mounts = {}          # full durable digest -> (permitted results, uuid8, uuid, label)
        self.sets = {}            # (post-step-1 digest, op, mode, inject) -> {d16: image}
        self.plans = {}           # plan trace digest -> [(inject, phase)]
        self.reached = {}         # (row, op, phase) -> set of observed categories

    # ------------------------------------------------------------ helpers

    def mount(self, img):
        d = M.digest(img)
        if d not in self.mounts:
            c = M.classify(img, "A", True)
            if c["result"] == ("TAPE_OK",):
                gp = M.gen(img["P"]) if M.sb_valid(img["P"]) else -1      # §4.1 candidate, as classify selects it
                gm = M.gen(img["M"]) if M.sb_valid(img["M"]) else -1
                sel = img["P"] if gp >= gm else img["M"]
                self.mounts[d] = (("TAPE_OK",), c["uuid"][:8], c["uuid"], sel[M.LABEL_OFFSET:M.LABEL_OFFSET + 32])
            else:
                self.mounts[d] = (c["result"], None, None, None)
        return self.mounts[d]

    def check_code(self, code, img, where):
        results, uuid8, _, _ = self.mount(img)
        if code.startswith("OK."):
            need(results == ("TAPE_OK",) and code[3:] == uuid8, f"{where}: mount {code} != model {results} {uuid8}")
        else:
            need(code in results, f"{where}: mount {code} not in permitted {list(results)}")

    @staticmethod
    def category(code, op):
        if code in UNM:
            return "unmountable"
        if code == "OK." + P.FRESH[op].hex()[:8]:
            return "completed"
        return "other:" + code

    def identity(self, img, op, where):
        """WP-10: no mount under the previous UUID or label (here: anything but the fresh identity)."""
        results, _, uuid, label = self.mount(img)
        if results == ("TAPE_OK",):
            need(uuid == P.FRESH[op].hex() and label == P.FINAL_SB[op][M.LABEL_OFFSET:M.LABEL_OFFSET + 32],
                 f"{where}: mounted under identity {uuid} label {label.rstrip(bytes(1))!r}, not the fresh one")

    def injections(self, ops, pre, scope):
        k = (P.trace_sha256(ops), scope)
        if k not in self.plans:
            self.plans[k] = P.rerun_injections(ops, P.step1_writes(pre), scope)
        return self.plans[k]

    def permitted(self, pre, ops, inject, mode, op, n_step1_ops):
        """{d16: image} a conforming device may hold. Past step 1 the image depends only on the post-step-1
        state (step 1 always ends with a flush), so those sets are shared across groups."""
        wk = sum(o[0] == "w" for o in ops[:n_step1_ops])
        fk = n_step1_ops - wk
        past = (inject[0] == "write" and inject[1] >= wk) or (inject[0] == "flush" and inject[1] >= fk)
        if past:
            post = M.apply(pre, ops[:n_step1_ops])
            key = (M.digest(post), op, mode, inject)
            if key not in self.sets:
                tail = ops[n_step1_ops:]
                rel = (inject[0], inject[1] - (wk if inject[0] == "write" else fk)) + tuple(inject[2:])
                self.sets[key] = {M.digest(i)[:16]: i for i in M.possible_images(post, tail, rel, mode)}
            return self.sets[key]
        return {M.digest(i)[:16]: i for i in M.possible_images(pre, ops, inject, mode)}

    # ------------------------------------------------------------ rows

    def check_rerun_rows(self, g, obs, outcome_only):
        op, mode = g["op"], g["mode"]
        pre, ops1, inject1 = P.precondition(g)
        ops = P.op_ops(op, pre)
        fresh8 = "OK." + P.FRESH[op].hex()[:8]
        # precondition
        if g["row"] == "R1":
            first = obs.get("first_run")
            need(isinstance(first, dict), "missing first_run")
            need(first.get("mount") in UNM, f"torn last fallback zero remounted {first.get('mount')}, not unmountable")
            if not outcome_only:
                need(first.get("trace_sha256") == P.trace_sha256(M.prefix(ops1, inject1)),
                     "first run is not the §4.5 generation-exhausted fallback order")
                need(first.get("durable_sha256") == M.digest(pre), "first-run durable image is not the torn last zero")
                self.check_code(first["mount"], pre, "precondition")
        else:
            pc = obs.get("precondition")
            need(isinstance(pc, dict) and pc.get("mount") in UNM, "residue fixture mounted")
            if not outcome_only:
                need(pc.get("durable_sha256") == M.digest(pre), "residue fixture bytes")
                self.check_code(pc["mount"], pre, "precondition")
        # uninterrupted re-run
        rerun = obs.get("rerun")
        need(isinstance(rerun, dict) and rerun.get("call") == {"fn": CALL[op], "result": "TAPE_OK", "more_work": False},
             "re-run on the same device did not complete")
        need(rerun.get("mount") == fresh8, f"completed re-run mounted {rerun.get('mount')}")
        final = M.apply(pre, ops)
        if not outcome_only:
            need(rerun.get("trace_sha256") == P.trace_sha256(ops),
                 "re-run is not tapefs §9.5/§9.6 from residue (zero mirror, flush, zero primary, flush, then step 2)")
            need(rerun.get("durable_sha256") == M.digest(final), "re-run did not reach the completed media")
        # injected re-runs
        inj = obs.get("injections")
        need(isinstance(inj, list), "missing injections")
        planned = self.injections(ops, pre, g["scope"])
        if not outcome_only:
            need(len(inj) == len(planned), f"{len(inj)} injections reported, {len(planned)} planned")
        n_step1_ops = len(M.step1_ops(pre))
        closure = obs.get("closure")
        closure_i = 0
        if g["row"] == "R2":
            need(isinstance(closure, list), "missing closure re-runs")
        for i, entry in enumerate(inj):
            need(isinstance(entry, str) and entry.count(" ") == 1, f"injection {i}: malformed {entry!r}")
            d16, code = entry.split(" ")
            where = f"injection {i}"
            if outcome_only:
                cat = self.category(code, op)
                need(cat in {"unmountable", "completed"},
                     f"{where}: mounted {code}: the destination's previous identity resurrected")
                continue
            (inject, phase) = planned[i]
            where += f" {list(inject)} [{phase}]"
            images = self.permitted(pre, ops, inject, mode, op, n_step1_ops)
            img = images.get(d16)
            need(img is not None, f"{where}: durable image {d16} is not one a conforming device may hold")
            self.check_code(code, img, where)
            cat = self.category(code, op)
            need(cat in PERMIT[phase], f"{where}: {code} is outside the §9.5/§9.6 rows for this phase")
            self.identity(img, op, where)
            self.reached.setdefault((g["row"], op, phase), set()).add(code if cat == "unmountable" else cat)
            if g["row"] == "R2" and phase == "residue":
                need(closure_i < len(closure), "closure re-runs missing")
                c = closure[closure_i]
                closure_i += 1
                need(isinstance(c, str) and c.count(" ") == 2, f"closure {closure_i}: malformed {c!r}")
                t16, f16, ccode = c.split(" ")
                xops = P.op_ops(op, img)
                need(t16 == P.trace_sha256(xops)[:16], f"{where}: re-run after a residue-zeroing interruption "
                                                        "is not §9.5/§9.6 from that state")
                need(f16 == M.digest(M.apply(img, xops))[:16] == M.digest(final)[:16],
                     f"{where}: re-run after a residue-zeroing interruption did not reach the completed media")
                need(ccode == fresh8, f"{where}: closure re-run mounted {ccode}")
        if g["row"] == "R2" and not outcome_only:
            need(closure_i == len(closure), "extra closure re-runs reported")
        if outcome_only and g["row"] == "R2":
            for c in closure:
                need(c.split(" ")[-1] == fresh8, f"closure re-run mounted {c}")

    def check_blank(self, g, obs, outcome_only):
        op = g["op"]
        img = P.blank(g["variant"])
        ops = P.op_ops(op, img)
        need(obs.get("call") == {"fn": CALL[op], "result": "TAPE_OK", "more_work": False}, "blank run did not complete")
        lbas = obs.get("write_lbas")
        need(isinstance(lbas, list) and lbas, "missing write_lbas")
        first_other = next((i for i, x in enumerate(lbas) if x not in SB_LBAS), len(lbas))
        need(first_other == 0, f"all-zero blank destination took {first_other} step-1 write(s)")
        need(sum(x in SB_LBAS for x in lbas) == 2, "blank run wrote a superblock more than the final mirror+primary")
        need(obs.get("mount") == "OK." + P.FRESH[op].hex()[:8], f"completed blank run mounted {obs.get('mount')}")
        if not outcome_only:
            need(lbas == [M.TRACKED[o[1]] for o in ops if o[0] == "w"], "write LBAs are not the planned order")
            need(obs.get("trace_sha256") == P.trace_sha256(ops), "blank trace is not tapefs §9.5/§9.6")
            need(obs.get("durable_sha256") == M.digest(M.apply(img, ops)), "blank run final media")

    def check(self, g, obs, outcome_only=False):
        _no_verdicts(obs)
        need(obs.get("schema") == SCHEMA, "schema")
        ident = {k: g[k] for k in P.IDENT if k in g}
        need({k: obs.get(k) for k in ident} == ident, f"group identity {ident}")
        if g["row"] == "R3":
            self.check_blank(g, obs, outcome_only)
        else:
            self.check_rerun_rows(g, obs, outcome_only)


def check_stream(lines, oracle=None):
    oracle = oracle or Oracle()
    groups = P.iter_groups()
    n = injections = 0
    for line in lines:
        g = next(groups, None)
        need(g is not None, "more observations than planned groups")
        obs = json.loads(line)
        try:
            oracle.check(g, obs)
        except AssertionError as e:
            raise AssertionError(f"group {g['index']} {g}: {e}") from None
        n += 1
        injections += len(obs.get("injections", []))
    need(next(groups, None) is None, "fewer observations than planned groups")
    return n, injections, oracle
