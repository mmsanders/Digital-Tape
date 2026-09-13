#!/usr/bin/env python3
"""Package self-test and targeted negative controls for P1-R2-V."""
from __future__ import annotations
import copy, gzip, json, shutil, subprocess, sys, tempfile
from pathlib import Path
import oracle
import generate_fixture
from oracle import VerificationError

HERE = Path(__file__).resolve().parent
NAMES = {"forward_1x":"forward-1x.pcm", "seek_boundaries":"seek-boundaries.pcm", "reverse_neg1x":"reverse-neg1x.pcm"}

def must_fail(label, fn):
    try:
        fn()
    except (VerificationError, ValueError, KeyError, json.JSONDecodeError, OSError):
        print("CAUGHT", label)
        return
    raise AssertionError("negative control did not fail: " + label)

def run_checked(raw, obs, outs):
    r = oracle.check_run(raw, obs, outs)
    if not r["pass"]:
        raise VerificationError("PCM mismatch")
    return r

def replay_rc(path):
    return subprocess.run(
        [sys.executable, str(HERE / "replay.py"), str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).returncode

def runner_cmd(evidence, adapter_cmd=None, adapter_source=None, timeout="2"):
    adapter_source = adapter_source or str(HERE / "_synthetic_adapter.py")
    adapter_cmd = adapter_cmd or f"{sys.executable} {HERE/'_synthetic_adapter.py'}"
    return [
        sys.executable, str(HERE / "runner.py"),
        "--adapter-cmd", adapter_cmd,
        "--adapter-kind", "synthetic",
        "--adapter-id", "verifier-synthetic-public-api-model-v1",
        "--adapter-source", adapter_source,
        "--adapter-build", "python3 source; self-test declaration",
        "--adapter-timeout-seconds", timeout,
        "--source-commit", "SELFTEST-DECLARED",
        "--source-tree", "SELFTEST-DECLARED",
        "--evidence-dir", str(evidence),
    ]

def main():
    generate_fixture.check_checked_in()
    print("PASS deterministic fixture/candidate-PCM regeneration")
    pkg = oracle.load_package(HERE)
    raw = gzip.decompress((HERE / pkg["fixture"]["archive"]).read_bytes())
    fx = oracle.verify_fixture(raw)
    assert tuple(fx["index"]["entries"]) == oracle.EXPECTED_ENTRIES
    exp = oracle.expected_outputs(raw)
    for family, rec in pkg["goldens"].items():
        assert (HERE / rec["path"]).read_bytes() == exp[family]
    print("PASS authenticated DRAFT-8 package + fixture-derived candidate PCM")

    with tempfile.TemporaryDirectory(prefix="playback-draft8-selftest-") as td_s:
        td = Path(td_s); out = td / "adapter"; out.mkdir()
        rawp = td / "fixture.vo08"; rawp.write_bytes(raw)
        subprocess.run([sys.executable, str(HERE / "_synthetic_adapter.py"), "--fixture", str(rawp), "--out-dir", str(out)], check=True, stdout=subprocess.PIPE)
        obs = json.loads((out / "observation.json").read_text())
        outs = {f:(out/n).read_bytes() for f,n in NAMES.items()}
        run_checked(raw, obs, outs)
        print("PASS synthetic three-family public-call/callback observation")

        bad = dict(outs); b = bytearray(bad["seek_boundaries"]); b[0:4] = exp["forward_1x"][4:8]; bad["seek_boundaries"] = bytes(b)
        if oracle.check_run(raw, obs, bad)["pass"]: raise AssertionError("wrong first seek frame escaped")
        print("CAUGHT wrong first frame after seek")

        bad = dict(outs); b = bytearray(bad["seek_boundaries"]); b[3*4:4*4] = exp["forward_1x"][6*4:7*4]; bad["seek_boundaries"] = bytes(b)
        if oracle.check_run(raw, obs, bad)["pass"]: raise AssertionError("run boundary +1 escaped")
        print("CAUGHT run-boundary off-by-one")

        bad = dict(outs); bad["reverse_neg1x"] = oracle.draft5_bad_reverse(raw)
        if oracle.check_run(raw, obs, bad)["pass"]: raise AssertionError("reverse grid drift escaped")
        print("CAUGHT reverse interpolation/grid drift")

        badobs = copy.deepcopy(obs); render_i = next(i for i,c in enumerate(badobs["cases"]["forward_1x"]["calls"]) if c["call"]=="tape_render")
        badobs["cases"]["forward_1x"]["callbacks"].append({"call_index":render_i,"op":"read","lba":2048,"count":1,"rc":0})
        must_fail("callback I/O during render", lambda: run_checked(raw,badobs,outs))
        badobs = copy.deepcopy(obs); seek = next(c for c in badobs["cases"]["seek_boundaries"]["calls"] if c["call"]=="tape_seek"); seek["frame"] += 1
        must_fail("wrong public tape_seek target", lambda: run_checked(raw,badobs,outs))

        tamper = td / "tamper-package"; shutil.copytree(HERE, tamper, ignore=shutil.ignore_patterns("__pycache__", "evidence"))
        p = tamper / pkg["fixture"]["archive"]; d=bytearray(p.read_bytes()); d[-1] ^= 1; p.write_bytes(d)
        must_fail("altered fixture bytes", lambda: oracle.load_package(tamper))
        shutil.rmtree(tamper); shutil.copytree(HERE, tamper, ignore=shutil.ignore_patterns("__pycache__", "evidence"))
        p = tamper / pkg["goldens"]["forward_1x"]["path"]; d=bytearray(p.read_bytes()); d[0] ^= 1; p.write_bytes(d)
        must_fail("altered candidate PCM bytes", lambda: oracle.load_package(tamper))
        shutil.rmtree(tamper); shutil.copytree(HERE, tamper, ignore=shutil.ignore_patterns("__pycache__", "evidence"))
        p=tamper/"spec/engine-api.md"; p.write_bytes(p.read_bytes()+b"\nTAMPER\n")
        must_fail("tampered authenticated spec bytes", lambda: oracle.load_package(tamper))

        ev = td / "evidence"
        cmd = runner_cmd(ev)
        subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        subprocess.run([sys.executable,str(HERE/"replay.py"),str(ev)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        print("PASS conforming synthetic offline saved-evidence replay")

        relabel=td/"manifest-relabel"; shutil.copytree(ev,relabel); p=relabel/"manifest.json"
        manifest=json.loads(p.read_text()); manifest["adapter"]["kind"]="product"
        p.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        if replay_rc(relabel)==0: raise AssertionError("manifest-only synthetic/product relabel escaped")
        print("CAUGHT manifest-only synthetic/product relabel")

        changed_id=td/"manifest-id"; shutil.copytree(ev,changed_id); p=changed_id/"manifest.json"
        manifest=json.loads(p.read_text()); manifest["adapter"]["id"]="different-adapter-id"
        p.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        if replay_rc(changed_id)==0: raise AssertionError("manifest-only adapter ID change escaped")
        print("CAUGHT manifest-only adapter ID mismatch")

        for field in ("source", "build"):
            missing_provenance=td/("missing-adapter-"+field); shutil.copytree(ev,missing_provenance)
            p=missing_provenance/"manifest.json"; manifest=json.loads(p.read_text())
            manifest["adapter"].pop(field)
            p.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
            if replay_rc(missing_provenance)==0:
                raise AssertionError(f"missing adapter {field} provenance escaped")
            print("CAUGHT missing adapter", field, "provenance")

        missing=td/"missing"; shutil.copytree(ev,missing); (missing/"output/seek-boundaries.pcm").unlink()
        if replay_rc(missing)==0: raise AssertionError("missing evidence replay escaped")
        print("CAUGHT missing evidence")
        changed=td/"changed"; shutil.copytree(ev,changed); p=changed/"output/reverse-neg1x.pcm"; d=bytearray(p.read_bytes()); d[0]^=1; p.write_bytes(d)
        if replay_rc(changed)==0: raise AssertionError("tampered evidence replay escaped")
        print("CAUGHT tampered evidence")
        changed_identity=td/"changed-identity"; shutil.copytree(ev,changed_identity); p=changed_identity/"manifest.json"; manifest=json.loads(p.read_text()); manifest["oracle_sha256"]="0"*64; p.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        if replay_rc(changed_identity)==0: raise AssertionError("tampered verifier identity escaped")
        print("CAUGHT tampered verifier identity")

        missing_exit=td/"missing-exit"; shutil.copytree(ev,missing_exit)
        (missing_exit/"output/adapter-exit.txt").unlink()
        p=missing_exit/"manifest.json"; manifest=json.loads(p.read_text())
        manifest["files"].pop("output/adapter-exit.txt")
        p.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        if replay_rc(missing_exit)==0: raise AssertionError("missing adapter exit escaped")
        print("CAUGHT missing recorded adapter exit")

        nonzero_adapter=td/"nonzero_adapter.py"
        nonzero_adapter.write_text("#!/usr/bin/env python3\nimport sys\nprint('intentional nonzero control')\nsys.exit(7)\n")
        nonzero=td/"nonzero-evidence"
        rc=subprocess.run(runner_cmd(nonzero, f"{sys.executable} {nonzero_adapter}", str(nonzero_adapter)),stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode
        if rc != 1: raise AssertionError(f"nonzero adapter runner returned {rc}, expected 1")
        manifest=json.loads((nonzero/"manifest.json").read_text())
        result=json.loads((nonzero/"result.json").read_text())
        assert (nonzero/"output/adapter-exit.txt").read_text()=="7\n"
        assert manifest["execution"]["outcome"]=="exited" and manifest["execution"]["exit_code"]==7
        assert result["error"]=="adapter exit 7"
        if replay_rc(nonzero)==0: raise AssertionError("nonzero adapter exit escaped replay")
        print("CAUGHT nonzero adapter exit with retained failure record")

        timeout_adapter=td/"timeout_adapter.py"
        timeout_adapter.write_text("#!/usr/bin/env python3\nimport time\nprint('starting timeout control', flush=True)\ntime.sleep(5)\n")
        timedout=td/"timeout-evidence"
        rc=subprocess.run(runner_cmd(timedout, f"{sys.executable} {timeout_adapter}", str(timeout_adapter), "0.05"),stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode
        if rc != 1: raise AssertionError(f"timeout runner returned {rc}, expected 1")
        manifest=json.loads((timedout/"manifest.json").read_text())
        result=json.loads((timedout/"result.json").read_text())
        assert (timedout/"output/adapter-exit.txt").read_text()=="TIMEOUT\n"
        assert manifest["execution"]["outcome"]=="timeout" and manifest["execution"]["exit_code"] is None
        assert result["error"].startswith("adapter timeout after ")
        if replay_rc(timedout)==0: raise AssertionError("timed-out adapter escaped replay")
        print("CAUGHT bounded adapter timeout with retained failure record")

        retained=td/"retained-evidence"; retained.mkdir(); sentinel=retained/"sentinel.bin"
        sentinel_bytes=b"PREEXISTING-EVIDENCE-MUST-SURVIVE\x00\xff"; sentinel.write_bytes(sentinel_bytes)
        rc=subprocess.run(runner_cmd(retained),stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode
        if rc != 2: raise AssertionError(f"nonempty destination runner returned {rc}, expected 2")
        if sentinel.read_bytes()!=sentinel_bytes or list(retained.iterdir()) != [sentinel]:
            raise AssertionError("runner changed a nonempty evidence destination")
        print("PASS nonempty evidence destination rejected with existing bytes retained")

    print("SELFTEST PASS: three families + identity/exit/provenance/replay/retention controls")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
