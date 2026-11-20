#!/usr/bin/env python3
"""tinyCAN — the bus between the policy and the motors, simulated and graded.

Everything else in the tiny family assumes a command reaches its motor instantly.
On the real Asimov-1 it does not. Menlo's own engineering slide gives the shape:

    RPU        Radxa CM5, firmware 200 Hz, one tick = 5,000 us
    motors     25 on 5 buses
    chips      6 x MCP2518FD CAN-FD, one per bus (5 motor buses + battery)
    SPI        spi4 <- right arm + left arm
               spi0 <- waist/neck + left leg
               spi1 <- right leg + battery
    poll       4,366 us modelled, sequential six-row firmware

4,366 of 5,000 us is 87% of the tick spent moving frames, before the controller
thinks. A policy tuned in a simulator that delivers commands instantly is tuned
against a robot that does not exist.

HONESTY ABOUT THE NUMBERS
Menlo published the AGGREGATE (4,366 us) and two throughput points (8/25 and
15/25 replies read at 1.67 ms). They did not publish per-frame SPI or CAN
timings. The per-frame constants below are a MODEL, calibrated so the sequential
poll lands near their published aggregate. They are assumptions, declared as
such, and every result carries `calibrated_to` so nobody mistakes a fitted model
for a measurement of their hardware.

WHAT IS REAL HERE
The topology is theirs, read off the slide. The contention rules are physical:
one frame per bus at a time, two chips share an SPI port so they serialize, and
a reply cannot be read before it arrives. Those constraints hold regardless of
the constants.

    python tinycan.py doctor
    python tinycan.py poll --mode rows
    python tinycan.py poll --mode burst
    python tinycan.py compare
    python tinycan.py grade --ref reference.json --cand candidate.json
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

TICK_US = 5000.0            # 200 Hz firmware
FIRMWARE_HZ = 200

# --- model constants (ASSUMPTIONS, calibrated to the published aggregate) -----
# Fitted to Menlo's three published points by grid search + local refine.
# Fit quality: rows@1.67ms 8/25 EXACT, burst@1.67ms 15/25 EXACT,
#              sequential aggregate 4836 us vs published 4366 us (+10.8%).
# The residual is declared, not hidden: this model is conservative on the
# deadline, so a policy that fits here has margin on their hardware.
SPI_WRITE_US = 8.0          # RPU -> chip, one command
SPI_READ_US = 8.0           # chip -> RPU, one reply
CAN_FRAME_US = 65.0         # one frame on the bus, one way
MOTOR_TURNAROUND_US = 40.0  # motor processes and answers
BURST_DISPATCH_US = 60.0    # RPU still issues each transfer even in PIO mode

# --- topology, read from Menlo's slide ---------------------------------------
CHIPS = [
    {"id": "right_arm",  "spi": "spi4", "motors": 5, "bus": "can0"},
    {"id": "left_arm",   "spi": "spi4", "motors": 5, "bus": "can1"},
    {"id": "waist_neck", "spi": "spi0", "motors": 3, "bus": "can2"},
    {"id": "left_leg",   "spi": "spi0", "motors": 6, "bus": "can3"},
    {"id": "right_leg",  "spi": "spi1", "motors": 6, "bus": "can4"},
    {"id": "battery",    "spi": "spi1", "motors": 0, "bus": "can5"},
]
MOTOR_TOTAL = sum(c["motors"] for c in CHIPS)   # 25


def _events(mode: str):
    """Discrete events for one poll. Returns (events, replies_read_at)."""
    spi_free = {p: 0.0 for p in {c["spi"] for c in CHIPS}}
    bus_free = {c["bus"]: 0.0 for c in CHIPS}
    rpu_free = 0.0
    ev = []
    replies = []
    for chip in CHIPS:
        n = max(1, chip["motors"])          # battery polls once
        for m in range(n):
            if mode == "rows":
                # sequential firmware: the row cannot start until the previous
                # row has fully finished, including reading its replies back.
                t = max(spi_free.values()) if ev else 0.0
                t = max([r[1] for r in replies], default=0.0)
            else:
                # burst: rows are dispatched back to back, but the RPU still
                # pays a per-transfer issue cost. A burst is not free.
                t = rpu_free
                rpu_free += BURST_DISPATCH_US
            # SPI write — two chips on one port serialize
            w0 = max(t, spi_free[chip["spi"]])
            w1 = w0 + SPI_WRITE_US
            spi_free[chip["spi"]] = w1
            ev.append((w0, w1, "spi_write", chip["id"], m))
            # CAN out — one frame per bus at a time
            c0 = max(w1, bus_free[chip["bus"]])
            c1 = c0 + CAN_FRAME_US
            ev.append((c0, c1, "can_out", chip["id"], m))
            # motor answers
            r0 = c1 + MOTOR_TURNAROUND_US
            r1 = r0 + CAN_FRAME_US
            bus_free[chip["bus"]] = r1
            ev.append((r0, r1, "can_reply", chip["id"], m))
            # SPI read back
            b0 = max(r1, spi_free[chip["spi"]])
            b1 = b0 + SPI_READ_US
            spi_free[chip["spi"]] = b1
            ev.append((b0, b1, "spi_read", chip["id"], m))
            if chip["motors"]:
                replies.append((chip["id"], b1, m))
    ev.sort(key=lambda e: e[0])
    return ev, replies


def poll(mode: str = "rows") -> dict:
    if mode not in ("rows", "burst"):
        raise ValueError(f"mode must be rows|burst, got {mode!r}")
    ev, replies = _events(mode)
    end = max(e[1] for e in ev)
    read_times = sorted(r[1] for r in replies)
    at_1670 = sum(1 for t in read_times if t <= 1670.0)
    return {
        "mode": mode,
        "firmware_hz": FIRMWARE_HZ,
        "tick_us": TICK_US,
        "motors": MOTOR_TOTAL,
        "buses": len([c for c in CHIPS if c["motors"]]),
        "chips": len(CHIPS),
        "spi_ports": len({c["spi"] for c in CHIPS}),
        "poll_end_us": round(end, 1),
        "fits_in_tick": end <= TICK_US,
        "tick_budget_used_pct": round(100 * end / TICK_US, 2),
        "headroom_us": round(TICK_US - end, 1),
        "replies_read": len(replies),
        "replies_by_1670us": at_1670,
        "events": len(ev),
        "calibrated_to": "Menlo published aggregate 4366 us (sequential rows); "
                         "per-frame constants are a model, not a measurement",
        "constants": {"spi_write_us": SPI_WRITE_US, "spi_read_us": SPI_READ_US,
                      "can_frame_us": CAN_FRAME_US,
                      "motor_turnaround_us": MOTOR_TURNAROUND_US,
                      "burst_dispatch_us": BURST_DISPATCH_US},
        "fit_quality": {"rows_at_1670us": "8/25 exact",
                        "burst_at_1670us": "15/25 exact",
                        "rows_aggregate": "4836 us model vs 4366 us published (+10.8%)",
                        "direction": "conservative — the model over-estimates the poll"},
    }


def trace_hash(mode: str) -> str:
    ev, _ = _events(mode)
    payload = [[round(a, 6), round(b, 6), k, c, m] for a, b, k, c, m in ev]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def compare() -> dict:
    a, b = poll("rows"), poll("burst")
    return {
        "rows": {k: a[k] for k in ("poll_end_us", "fits_in_tick", "tick_budget_used_pct",
                                   "replies_by_1670us")},
        "burst": {k: b[k] for k in ("poll_end_us", "fits_in_tick", "tick_budget_used_pct",
                                    "replies_by_1670us")},
        "speedup": round(a["poll_end_us"] / b["poll_end_us"], 3),
        "headroom_gained_us": round(b["headroom_us"] - a["headroom_us"], 1),
        "published_reference": {"poll_end_us": 4366, "rows_read_at_1670us": 8,
                                "burst_read_at_1670us": 15,
                                "source": "Menlo engineering slide, one 5 ms tick"},
        "note": "the model is calibrated to the aggregate; the throughput split is "
                "a prediction of the model, not a measurement of their firmware",
    }


def grade(ref: dict, cand: dict) -> dict:
    """Same topology and constants => same event trace => reward 1.0."""
    same = ref.get("trace_sha256") == cand.get("trace_sha256")
    return {"reward": 1.0 if same else 0.0, "tokens_used": 0, "method": "byte_compare",
            "reference": (ref.get("trace_sha256") or "")[:16],
            "candidate": (cand.get("trace_sha256") or "")[:16],
            "fits_in_tick": cand.get("fits_in_tick"),
            "note": "grading the event trace, not the summary — two polls with the "
                    "same end time but different ordering are different polls"}


def doctor() -> dict:
    return {"ok": True, "module": "tinycan", "deps": "stdlib only",
            "topology": "Asimov-1, 25 motors / 5 buses / 6 MCP2518FD / 3 SPI ports",
            "topology_source": "Menlo engineering slide",
            "firmware_hz": FIRMWARE_HZ, "tick_us": TICK_US,
            "model_constants_are_assumptions": True}


def main() -> int:
    ap = argparse.ArgumentParser(description="tinyCAN — the bus, simulated and graded")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("compare")
    p = sub.add_parser("poll"); p.add_argument("--mode", default="rows"); p.add_argument("--out")
    g = sub.add_parser("grade"); g.add_argument("--ref", required=True); g.add_argument("--cand", required=True)
    a = ap.parse_args()
    if a.cmd == "doctor":
        print(json.dumps(doctor(), indent=2)); return 0
    if a.cmd == "compare":
        print(json.dumps(compare(), indent=2)); return 0
    if a.cmd == "poll":
        r = poll(a.mode); r["trace_sha256"] = trace_hash(a.mode)
        if a.out: Path(a.out).write_text(json.dumps(r, indent=2), encoding="utf-8")
        print(json.dumps(r, indent=2)); return 0 if r["fits_in_tick"] else 1
    if a.cmd == "grade":
        ref = json.loads(Path(a.ref).read_text(encoding="utf-8"))
        cand = json.loads(Path(a.cand).read_text(encoding="utf-8"))
        r = grade(ref, cand); print(json.dumps(r, indent=2)); return 0 if r["reward"] == 1.0 else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
