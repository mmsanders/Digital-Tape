#!/usr/bin/env python3
"""#451: the SHIPPING ingest binary under a bounded-memory limit, for census case
resources/exhaustion (case 1926). Software's observation supplement to candidate
6126d04's Stage1 packets, whose case 1926 ran only the observation build. It judges
nothing: Verification disposes.

The candidate is unchanged. Case inputs come from the packet transport's own
setup_case (host/ingest/stage1/run_packet.py at 6126d04), so the inputs are the
packet's. For each memory limit the binary is run three ways:

  version   `ingest --version` under the limit: proves the binary loads and runs its
            own code at that limit, so a failure below is not a loader failure;
  case      the case's argv under the limit: exit, stderr, and the cleanup facts
            (DEST absent, no owned stage left, unrelated sentinel unchanged);
  positive  once, with no limit: the same inputs publish (exit 0), so the limit is
            what fails the case.

Limits: Linux prlimit RLIMIT_AS, Windows a Job object with
JOB_OBJECT_LIMIT_PROCESS_MEMORY (the packet's own methods), swept around the
packet's value. macOS has no enforced address-space or commit limit for an
ordinary process; the run records what setrlimit does there instead of claiming
an exhaustion.

  shipping_exhaustion.py --package DIR --sources DIR --bin PATH --expect-sha256 HEX --out DIR
"""
import argparse, json, os, platform, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "host" / "ingest" / "stage1"))
import run_packet as rp  # noqa: E402  (the candidate's own transport, unchanged)

MIB = 1 << 20
SWEEP = {
    "linux": [4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128],
    "windows": [2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128],
    "macos": [6, 64],
}


def plat():
    s = platform.system()
    return {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}[s]


def run_limited(argv, limit, cwd=None):
    """Run argv with `limit` bytes (None: unlimited). Returns a result dict."""
    p_id = plat()
    r = {"limit_bytes": limit}
    job = None
    cmd = list(argv)
    pre = None
    if limit is not None:
        if p_id == "linux":
            cmd = ["prlimit", f"--as={limit}", "--"] + cmd
            r["method"] = "prlimit RLIMIT_AS"
        elif p_id == "windows":
            job = rp.windows_memory_job(limit)
            r["method"] = "Job object JOB_OBJECT_LIMIT_PROCESS_MEMORY"
        else:
            import resource
            r["method"] = "setrlimit RLIMIT_AS and RLIMIT_DATA (macOS)"
            got = {}

            def pre():  # runs in the child before exec; report via exit code would lose it
                for name in ("RLIMIT_AS", "RLIMIT_DATA"):
                    try:
                        resource.setrlimit(getattr(resource, name), (limit, limit))
                    except (ValueError, OSError):
                        pass
            # Probe in this process (a throwaway fork would hide it): does setrlimit accept it?
            for name in ("RLIMIT_AS", "RLIMIT_DATA"):
                q = subprocess.run([sys.executable, "-c",
                                    f"import resource;resource.setrlimit(resource.{name},({limit},{limit}));"
                                    f"print(resource.getrlimit(resource.{name}))"], capture_output=True, text=True)
                got[name] = {"exit": q.returncode, "stdout": q.stdout.strip(), "stderr": q.stderr.strip()[-200:]}
            r["setrlimit_probe"] = got
    flags = 0x4 if job is not None else 0
    if os.name == "nt":
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, creationflags=flags)
        if job is not None:
            rp.windows_job_assign_and_resume(job, p)
    else:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, preexec_fn=pre)
    out, err = p.communicate()
    r["exit"] = p.returncode
    if os.name == "nt":
        r["exit_hex"] = f"0x{p.returncode & 0xFFFFFFFF:08X}"
    if job is not None:
        r["job_peak_process_memory"] = rp.windows_job_peak(job)
    r["stdout_head"] = out[:200].decode("utf-8", "replace")
    r["stderr"] = err[:600].decode("utf-8", "replace")
    r["own_diagnostic"] = err.decode("utf-8", "replace").startswith("ingest:")
    r["out_of_memory_diagnostic"] = b"out of memory" in err
    return r


def cleanup_facts(dest, before_unrelated):
    stage_prefix = "." + dest.name + ".ingest-stage-"
    names, _ = rp.snapshot(dest)
    return {"dest_exists": dest.exists(), "dest_entries": names,
            "owned_stage_left": sorted(x.name for x in dest.parent.iterdir() if x.name.startswith(stage_prefix)),
            "out_dir_entries": sorted(x.name for x in dest.parent.iterdir()),
            "unrelated_unchanged": rp.sha_file(dest.parent / "unrelated.txt") == before_unrelated}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--expect-sha256", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    binp = os.path.abspath(a.bin)
    p_id = plat()
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    n = next(i for i, c in enumerate(census) if c["id"] == "resources/exhaustion")
    case = census[n]
    res = {"case_index": n, "case": case, "platform": p_id, "os": platform.platform(),
           "binary": os.path.basename(binp), "binary_sha256": rp.sha_file(binp),
           "expected_shipping_sha256": a.expect_sha256}
    res["binary_is_exact_shipping"] = res["binary_sha256"] == a.expect_sha256
    res["packet_method"] = rp.EXHAUST.get(p_id)
    assets = Path(a.sources) / "assets"

    def fresh():
        w = Path(tempfile.mkdtemp(prefix="exh-"))
        tail, dest, env, notes, capability = rp.setup_case(case, w, assets)
        assert not env, env  # case 1926 carries no seam environment for the shipping run
        return w, tail, dest

    w, tail, dest = fresh()
    unrel = rp.sha_file(dest.parent / "unrelated.txt")
    res["argv"] = [os.path.basename(binp)] + [rp.raw_arg(x) for x in tail]
    pos = run_limited([binp] + tail, None)
    pos.update(cleanup_facts(dest, unrel))
    if pos["exit"] == 0:
        pos["published"] = {k: rp.sha_file(dest / k) for k in ("audio.wav", "manifest.json")}
    res["positive_unlimited"] = pos
    shutil.rmtree(w, ignore_errors=True)

    sweep = []
    for mib in SWEEP[p_id]:
        limit = mib * MIB
        row = {"limit_mib": mib, "version": run_limited([binp, "--version"], limit)}
        w, tail, dest = fresh()
        unrel = rp.sha_file(dest.parent / "unrelated.txt")
        c = run_limited([binp] + tail, limit)
        c.update(cleanup_facts(dest, unrel))
        row["case"] = c
        shutil.rmtree(w, ignore_errors=True)
        v, c = row["version"], row["case"]
        row["verdict_facts"] = {
            "binary_runs_at_limit": v["exit"] == 0 and v["stdout_head"].startswith("ingest"),
            "case_exit": c["exit"], "case_own_oom_diagnostic": c["own_diagnostic"] and c["out_of_memory_diagnostic"],
            "clean": (not c["dest_exists"]) and not c["owned_stage_left"] and c["unrelated_unchanged"]
                     and c["out_dir_entries"] == ["unrelated.txt"],
        }
        sweep.append(row)
        f = row["verdict_facts"]
        print(f"{p_id} {mib:4d} MiB: version {v['exit']} | case exit {c['exit']} oom-diag {f['case_own_oom_diagnostic']} "
              f"clean {f['clean']} | {c['stderr'][:120]!r}", flush=True)
    res["sweep"] = sweep
    res["exhaustion_rows"] = [r["limit_mib"] for r in sweep
                              if r["verdict_facts"]["binary_runs_at_limit"] and r["verdict_facts"]["case_exit"] == 1
                              and r["verdict_facts"]["case_own_oom_diagnostic"] and r["verdict_facts"]["clean"]]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"shipping-exhaustion-{p_id}.json").write_bytes(rp.canonical(res))
    print(json.dumps({"platform": p_id, "binary_is_exact_shipping": res["binary_is_exact_shipping"],
                      "binary_sha256": res["binary_sha256"], "positive_exit": pos["exit"],
                      "exhaustion_rows_mib": res["exhaustion_rows"]}))


if __name__ == "__main__":
    main()
