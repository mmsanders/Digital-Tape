#!/usr/bin/env python3
"""Generate synthetic public observations and kill five arithmetic red controls."""
import copy
import hashlib
import struct
import zlib

from oracle import RUN_LENGTHS, Transport, cases, check, digest_plan, fixture, pcm, schedules


def raw_media():
    runs, _ = fixture()
    sb = bytearray(512)
    sb[:8] = b"TAPEFS\0\x01"
    struct.pack_into("<I", sb, 52, 100)
    struct.pack_into("<I", sb, 56, 1)
    struct.pack_into("<I", sb, 508, zlib.crc32(sb[:508]))
    header = bytearray(512)
    header[:8] = b"TAPEIDX\x01"
    struct.pack_into("<IB3xIQ", header, 8, 10, 1, 4, sum(RUN_LENGTHS))
    entries = b"".join(struct.pack("<III", j + 1, 0, len(run)) for j, run in enumerate(runs))
    struct.pack_into("<I", header, 60, zlib.crc32(header[:60] + entries))
    chunks = {}
    for j, run in enumerate(runs):
        b = bytearray(512)
        content = pcm(run)
        b[:len(content)] = content
        chunks[str(2048 + (j + 1) * 1024)] = b.hex()
    return {"superblock": sb.hex(), "B0": {"header": header.hex(), "entries": entries.hex()},
            "B1": {"header": bytes(512).hex(), "entries": ""}, "chunks": chunks}


def observation(case):
    _, frames = fixture()
    obs = {"schema": "wp08-r44-v1", "case": case.id,
           "raw_media": raw_media(), "seek": case.seek, "rate": case.rate, "variants": {}}
    for label, schedule in schedules(case.count).items():
        budget = {"whole": 256, "single": 1, "uneven": 7}[label]
        model = Transport(frames, case.seek, case.rate)
        renders = []
        for requested in schedule:
            emitted = model.render(requested)
            renders.append({"requested": requested, "result": "TAPE_OK", "rendered": len(emitted),
                            "pcm_hex": pcm(emitted).hex(), "tell": model.pos >> 32,
                            "at_start": model.at_start, "at_end": model.at_end,
                            "block_events": []})
        obs["variants"][label] = {"render_sizes": schedule, "service_budget": budget,
                                   "services": [{"budget": budget, "events": [{"op": "read", "lba": 2048, "count": 4}],
                                                 "result": "TAPE_OK", "more_work": False}]
                                   if budget >= 4 else
                                   [{"budget": budget, "events": [{"op": "read", "lba": 2048 + j, "count": 1}],
                                     "result": "TAPE_OK",
                                     "more_work": j < 3} for j in range(4)],
                                   "renders": renders}
    return obs


def run():
    plan = cases()
    by_id = {c.id: c for c in plan}
    for case in plan:
        check(case, observation(case))
    spoof = observation(plan[0])
    spoof.update(fixture_sha256="0" * 64, run_lengths=[17])
    spoof["variants"]["whole"]["services"][0]["blocks"] = 0
    check(plan[0], spoof)  # adapter labels cannot authenticate raw observations
    controls = [
        ("seek off by one", "boundary-5+0-f", lambda o: o["variants"]["whole"]["renders"][0].update(tell=0)),
        ("stale run sample", "boundary-8+0-r", lambda o: o["variants"]["whole"]["renders"][0].update(pcm_hex="00000000" + o["variants"]["whole"]["renders"][0]["pcm_hex"][8:])),
        ("wrong negative interpolation rounding", "fraction-2", lambda o: o["variants"]["single"]["renders"][1].update(pcm_hex="00000000")),
        ("endpoint wrap", "huge-forward", lambda o: o["variants"]["whole"]["renders"][0].update(tell=0)),
        ("service-time drift", "fraction-3", lambda o: o["variants"]["uneven"]["renders"][0].update(pcm_hex="00000000")),
        ("raw run mapping", "boundary-5+0-f", lambda o: o["raw_media"]["B0"].update(entries="00000000" + o["raw_media"]["B0"]["entries"][8:])),
        ("raw chunk PCM", "boundary-8+0-f", lambda o: o["raw_media"]["chunks"].update({"3072": "0000" + o["raw_media"]["chunks"]["3072"][4:]})),
        ("service over budget", "fraction-1", lambda o: o["variants"]["single"]["services"][0]["events"][0].update(count=2)),
        ("render raw I/O", "fraction-4", lambda o: o["variants"]["whole"]["renders"][0]["block_events"].append({"op": "read", "lba": 3072, "count": 1})),
    ]
    for name, key, mutate in controls:
        obs = copy.deepcopy(observation(by_id[key]))
        mutate(obs)
        try:
            check(by_id[key], obs)
        except AssertionError:
            pass
        else:
            raise AssertionError("red control survived: " + name)
    print("PASS", len(plan), "synthetic cases;", len(controls),
          "red controls killed; spoofed labels ignored; plan", digest_plan())


if __name__ == "__main__":
    run()
