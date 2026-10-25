# One admitted Verification318 metadata-only tapectl cards attempt. Binds identity and
# context immediately before launch, runs exactly once, retains original bytes.
import ctypes, datetime, getpass, hashlib, json, os, platform, shutil, subprocess, sys

ROOT = r"C:\Users\mrtro\claude\software-only\live578"
SRC = r"C:\Users\mrtro\claude\software-only\live578-download\tapectl.exe"
EXE = ROOT + r"\tapectl.exe"
JOB = ROOT + r"\job"
NONCE = "154abcdcabdabea5199b812735fbe464"
REPORT = JOB + rf"\cards-{NONCE}.jsonl"
ARGV = [EXE, "cards", "--report", REPORT, "--report-nonce", NONCE]
SHA = "44ef26869ba2d01a8a183660a2c7a050d0e7e9ff37c40b727131512739ea6ded"
RECEIPTS = ROOT + r"\receipts"

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def stop(why):
    print("STOP:", why); sys.exit(3)

if os.path.exists(ROOT): stop("live578 already exists")
os.makedirs(JOB); os.makedirs(RECEIPTS)
shutil.copyfile(SRC, EXE)
pre = {
    "exe": EXE, "exe_sha256": sha(EXE), "exe_bytes": os.path.getsize(EXE), "cwd": JOB, "argv": ARGV,
    "job_entries_before": os.listdir(JOB), "report_exists_before": os.path.exists(REPORT),
    "user": getpass.getuser(), "elevated": bool(ctypes.windll.shell32.IsUserAnAdmin()),
    "os": platform.platform(), "python": sys.version.split()[0],
    "caller": "Claude Code desktop, Opus 5.5, auto mode (caller declaration)",
    "admission": "Verification318 fdffea5759c2cf48b37a6960c5ed36d09ab91b98 findings/P2-318-CORRECTION1-2026-10-25",
    "michael_chat_approval": "Go ahead and run",
}
if pre["exe_sha256"] != SHA: stop("hash differs")
if pre["job_entries_before"] or pre["report_exists_before"]: stop("job not empty")
if pre["user"] != "mrtro" or pre["elevated"]: stop("context differs")
pre["started_utc"] = now()
json.dump(pre, open(RECEIPTS + r"\invocation.json", "w"), indent=2)
try:
    p = subprocess.run(ARGV, cwd=JOB, capture_output=True, shell=False, timeout=60)
    out, err, code, note = p.stdout, p.stderr, p.returncode, None
except subprocess.TimeoutExpired as e:
    out, err, code, note = e.stdout or b"", e.stderr or b"", None, "timed out after 60 s and was killed"
except OSError as e:
    out, err, code, note = b"", b"", None, f"launch failed: {e}"
post = {"ended_utc": now(), "exit": code, "note": note, "stdout_bytes": len(out), "stderr_bytes": len(err),
        "report_exists": os.path.exists(REPORT), "job_entries_after": os.listdir(JOB)}
open(RECEIPTS + r"\stdout.bin", "wb").write(out)
open(RECEIPTS + r"\stderr.bin", "wb").write(err)
for name in ["stdout.bin", "stderr.bin"]: post[name + "_sha256"] = sha(RECEIPTS + "\\" + name)
if post["report_exists"]: post["report_sha256"] = sha(REPORT)
json.dump(post, open(RECEIPTS + r"\terminal.json", "w"), indent=2)
print(json.dumps({k: v for k, v in post.items()}, indent=2))
