#!/usr/bin/env python3
"""#461: package the corrected Windows 11 INGEST collection kit.

Packages the exact binaries the kit job built from one source commit, as
host/ingest/stage1/win11_packet.ps1 expects them (ingest.exe, observe/ingest.exe,
profile/), plus KIT.json recording their provenance. Nothing is rebuilt or
substituted here: the hashes recorded are of the bytes packaged.

Writes, in --out:
  win11-kit.zip           ZIP64-capable deflate archive (members in a fixed order)
  KIT-INVENTORY.json      archive size and SHA-256, and every member's name, size,
                          SHA-256 and compressed size, re-read from the written zip
  SHA256SUMS              the archive and the inventory

  build_kit.py --shipping EXE --observe EXE --profile DIR --source-commit SHA
               --source-tree SHA --toolchain FILE --out DIR
"""
import argparse, hashlib, json, subprocess, sys, zipfile
from pathlib import Path


def sha(b):
    return hashlib.sha256(b).hexdigest()


def version(exe):
    return subprocess.run([str(exe), "--version"], capture_output=True, text=True, check=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("shipping", "observe", "profile", "source-commit", "source-tree", "toolchain", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    members = [("ingest.exe", Path(a.shipping)), ("observe/ingest.exe", Path(a.observe))]
    prof = Path(a.profile)
    members += [("profile/" + p.relative_to(prof).as_posix(), p) for p in sorted(prof.rglob("*")) if p.is_file()]
    kit = {
        "kit": "INGEST-1 Windows 11 collection kit (#461)",
        "source_repo": "mmsanders/Digital-Tape",
        "source_commit": a.source_commit,
        "source_tree": a.source_tree,
        "shipping": {"member": "ingest.exe", "sha256": sha(Path(a.shipping).read_bytes()),
                     "version": version(a.shipping),
                     "build": "cargo build --release --locked (host/ingest)"},
        "observation": {"member": "observe/ingest.exe", "sha256": sha(Path(a.observe).read_bytes()),
                        "version": version(a.observe),
                        "build": "cargo build --release --locked --features observe --target-dir target/observe (host/ingest)"},
        "profile": "cargo run --release --locked --example profile_file -- <dir> (host/ingest)",
        "toolchain": Path(a.toolchain).read_text(encoding="utf-8"),
        "status": "NOT READY FOR MICHAEL pending exact-kit authentication by Verification #204",
    }
    kit_json = (json.dumps(kit, indent=1, sort_keys=True) + "\n").encode()
    zpath = out / "win11-kit.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for name, p in members:
            z.write(p, name)
        z.writestr("KIT.json", kit_json)
    # Re-read the archive actually written: the inventory describes these bytes.
    inv = []
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            sys.exit(f"archive member {bad} fails its CRC")
        for i in z.infolist():
            data = z.read(i)
            inv.append({"name": i.filename, "size": i.file_size, "compressed": i.compress_size, "sha256": sha(data)})
    want = {n: sha(p.read_bytes()) for n, p in members}
    want["KIT.json"] = sha(kit_json)
    if {m["name"]: m["sha256"] for m in inv} != want:
        sys.exit("archive members differ from the packaged files")
    zb = zpath.read_bytes()
    inventory = {"archive": "win11-kit.zip", "size": len(zb), "sha256": sha(zb), "members": inv,
                 "source_commit": a.source_commit, "shipping_sha256": kit["shipping"]["sha256"],
                 "observation_sha256": kit["observation"]["sha256"]}
    ib = (json.dumps(inventory, indent=1) + "\n").encode()
    (out / "KIT-INVENTORY.json").write_bytes(ib)
    (out / "SHA256SUMS").write_text(f"{sha(zb)}  win11-kit.zip\n{sha(ib)}  KIT-INVENTORY.json\n")
    print(json.dumps({k: v for k, v in inventory.items() if k != "members"}, indent=1))
    for m in inv:
        print(f"  {m['sha256']}  {m['size']:>10}  {m['name']}")


if __name__ == "__main__":
    main()
