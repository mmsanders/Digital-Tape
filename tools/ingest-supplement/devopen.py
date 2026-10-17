#!/usr/bin/env python3
"""#451: can a native Windows observer see device-open ATTEMPTS by a process, not
only successful file-system opens? Controls and scanners for
windows_device_open.ps1. It judges nothing; the summary states, per tracer and per
control, whether a record naming the device was attributed to that control's PID.

  devopen.py touch MODE PATH          MODE: open0 (zero access), openread (GENERIC_READ),
                                      file (ordinary file, read)
  devopen.py procmon-config OUT.pmc   Procmon filter: python.exe only, no registry/network
  devopen.py scan-procmon CSV CONTROLS.jsonl DISK
  devopen.py scan-etw XML CONTROLS.jsonl DISK
"""
import csv, json, os, re, sys

GENERIC_READ = 0x80000000


def touch(mode, path):
    import ctypes
    from ctypes import wintypes as W
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.restype = W.HANDLE
    k.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE]
    access = {"open0": 0, "openread": GENERIC_READ, "file": GENERIC_READ}[mode]
    h = k.CreateFileW(path, access, 3, None, 3, 0, None)
    ok = h not in (None, W.HANDLE(-1).value)
    err = 0 if ok else ctypes.get_last_error()
    if ok:
        k.CloseHandle(h)
    print(json.dumps({"pid": os.getpid(), "mode": mode, "path": path, "ok": ok, "win32": err}), flush=True)


def procmon_config(out):
    from procmon_parser import Rule, dump_configuration
    rules = [Rule("Process_Name", "is", "python.exe", "include"),
             Rule("Event_Class", "is", "Registry", "exclude"),
             Rule("Event_Class", "is", "Network", "exclude"),
             Rule("Event_Class", "is", "Profiling", "exclude")]
    with open(out, "wb") as f:
        dump_configuration({"FilterRules": rules, "DestructiveFilter": 1}, f)


def needles(disk):
    """Names under which an open of disk N, or of the absent PhysicalDrive99, can appear."""
    words = [f"PhysicalDrive{disk}", f"Harddisk{disk}\\DR", f"Harddisk{disk}\\Partition0", "PhysicalDrive99"]
    return words, [w.encode("utf-16-le").hex().upper() for w in words]


def controls(path):
    return [json.loads(l) for l in open(path, encoding="utf-8-sig") if l.strip().startswith("{")]


def scan_procmon(csvp, ctl, disk):
    words, _ = needles(disk)
    ctl = controls(ctl)
    rows = list(csv.reader(open(csvp, encoding="utf-8-sig", errors="replace", newline="")))
    head, rows = rows[0], rows[1:]
    c = {n: i for i, n in enumerate(head)}
    out = []
    for t in ctl:
        hits = [{"op": r[c["Operation"]], "path": r[c["Path"]], "result": r[c["Result"]]}
                for r in rows if r[c["PID"]] == str(t["pid"]) and any(w.lower() in r[c["Path"]].lower() for w in words)]
        out.append({**t, "records_for_pid": sum(1 for r in rows if r[c["PID"]] == str(t["pid"])),
                    "device_records": hits[:6], "detected": bool(hits)})
    print(json.dumps({"tracer": "procmon", "csv_rows": len(rows), "controls": out}, indent=1))


def scan_etw(xmlp, ctl, disk):
    import xml.etree.ElementTree as ET
    words, hexes = needles(disk)
    ctl = controls(ctl)
    pids = {t["pid"]: {"records": 0, "hits": [], "events": {}} for t in ctl}
    total = 0
    for _, el in ET.iterparse(xmlp):
        if not el.tag.endswith("Event"):
            continue
        total += 1
        ex = next((e for e in el.iter() if e.tag.endswith("Execution")), None)
        pid = int(ex.get("ProcessID", "-1"), 0) if ex is not None else -1
        if pid in pids:
            s = pids[pid]
            s["records"] += 1
            task = next((e.text for e in el.iter() if e.tag.endswith("Task") and e.text), "?")
            op = next((e.text for e in el.iter() if e.tag.endswith("Opcode") and e.text), "?")
            key = f"{task}/{op}"
            s["events"][key] = s["events"].get(key, 0) + 1
            for d in el.iter():
                if not d.tag.endswith("Data") or not d.text:
                    continue
                txt, up = d.text, d.text.upper()
                if any(w.lower() in txt.lower() for w in words) or any(h in up for h in hexes):
                    if len(s["hits"]) < 6:
                        s["hits"].append({"event": key, "field": d.get("Name"), "value": txt[:300]})
        el.clear()
    out = [{**t, "records_for_pid": pids[t["pid"]]["records"], "events": pids[t["pid"]]["events"],
            "device_records": pids[t["pid"]]["hits"], "detected": bool(pids[t["pid"]]["hits"])} for t in ctl]
    print(json.dumps({"tracer": os.path.basename(xmlp), "events": total, "controls": out}, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    {"touch": lambda: touch(a[1], a[2]), "procmon-config": lambda: procmon_config(a[1]),
     "scan-procmon": lambda: scan_procmon(a[1], a[2], int(a[3])),
     "scan-etw": lambda: scan_etw(a[1], a[2], int(a[3]))}[a[0]]()
