#!/usr/bin/env python3
"""
make_fixture.py — synthetic NYC-taxi-shaped CSV with deliberately planted defects.

This is NOT sample data and must never be mistaken for the Kaggle dataset. Every row is
generated, and roughly one in six carries a specific, known defect so the pipeline can be
verified end to end before real data exists: each DQ rule has something to catch, and each
counted total is predictable.

The planted defects and their expected handling are asserted in tests/test_pipeline_e2e.py.
"""

import argparse
import csv
import hashlib
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

# Manhattan-ish box, used only to generate plausible-looking points. The real geographic
# bounds are a TBD threshold (DQ-009/010) and are deliberately not decided here.
LAT_LO, LAT_HI = 40.70, 40.80
LON_LO, LON_HI = -74.02, -73.93
BASE = datetime(2016, 1, 1)

# Every planted defect, its rule, and what the pipeline must do with it.
PLANTED = {
    "null_id":            ("DQ-001", "reject"),
    "dup_exact":          ("DQ-002", "reject"),   # identical payload  -> type A
    "dup_conflicting":    ("DQ-002", "reject"),   # same id, different -> type C
    "null_pickup":        ("DQ-004", "reject"),
    "null_dropoff":       ("DQ-005", "reject"),
    "dropoff_before":     ("DQ-006", "reject"),
    "zero_duration":      ("DQ-007", "reject"),
    "negative_duration":  ("DQ-007", "reject"),
    "zero_passengers":    ("DQ-008", "flag"),     # flagged, NOT rejected (spec OQ-5)
    "bad_flag_value":     ("DQ-011", "flag"),
    "null_coord":         ("GEO-001", "reject"),
    "origin_coord":       ("GEO-004", "reject"),  # (0,0) — passes worldwide bounds, wrong city
    "same_point":         ("GEO-005", "keep"),    # pickup == dropoff is legitimate
    "duration_mismatch":  ("CONSISTENCY", "keep"),  # trip_duration disagrees with the timestamps
    "extreme_duration":   ("OUTLIER", "keep"),    # 20h trip: flagged, retained, still counted
}


def rnd_point(rng):
    return round(rng.uniform(LAT_LO, LAT_HI), 6), round(rng.uniform(LON_LO, LON_HI), 6)


def haversine_km(lat1, lon1, lat2, lon2):
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def build(n_clean, seed):
    rng = random.Random(seed)
    rows, expected = [], {k: 0 for k in PLANTED}

    def base_row(i, defect=""):
        plat, plon = rnd_point(rng)
        dlat, dlon = rnd_point(rng)
        pickup = BASE + timedelta(minutes=rng.randint(0, 60 * 24 * 120))
        # Duration correlated with distance so speed lands in a plausible range.
        km = haversine_km(plat, plon, dlat, dlon)
        dur = max(60, int(km / max(rng.uniform(8, 28), 1) * 3600) + rng.randint(-60, 180))
        return {
            "id": f"id{i:07d}",
            "vendor_id": rng.choice([1, 2]),
            "pickup_datetime": pickup.strftime("%Y-%m-%d %H:%M:%S"),
            "dropoff_datetime": (pickup + timedelta(seconds=dur)).strftime("%Y-%m-%d %H:%M:%S"),
            "passenger_count": rng.choice([1, 1, 1, 2, 2, 3, 4, 5, 6]),
            "pickup_longitude": plon, "pickup_latitude": plat,
            "dropoff_longitude": dlon, "dropoff_latitude": dlat,
            "store_and_fwd_flag": rng.choice(["N"] * 30 + ["Y"]),
            "trip_duration": dur,
            "_defect": defect,
        }

    for i in range(n_clean):
        rows.append(base_row(i))

    i = n_clean
    def add(defect, mutate):
        nonlocal i
        r = base_row(i, defect); mutate(r); rows.append(r)
        expected[defect] += 1; i += 1

    def set_ts(r, pickup, dur):
        r["pickup_datetime"] = pickup.strftime("%Y-%m-%d %H:%M:%S")
        r["dropoff_datetime"] = (pickup + timedelta(seconds=dur)).strftime("%Y-%m-%d %H:%M:%S")
        r["trip_duration"] = dur

    for _ in range(3):  add("null_id",           lambda r: r.update(id=""))
    for _ in range(2):  add("null_pickup",       lambda r: r.update(pickup_datetime=""))
    for _ in range(2):  add("null_dropoff",      lambda r: r.update(dropoff_datetime=""))
    for _ in range(4):  add("dropoff_before",    lambda r: set_ts(r, BASE + timedelta(days=5), -600))
    for _ in range(3):  add("zero_duration",     lambda r: r.update(trip_duration=0))
    for _ in range(2):  add("negative_duration", lambda r: r.update(trip_duration=-45))
    for _ in range(5):  add("zero_passengers",   lambda r: r.update(passenger_count=0))
    for _ in range(3):  add("bad_flag_value",    lambda r: r.update(store_and_fwd_flag="y"))
    for _ in range(2):  add("null_coord",        lambda r: r.update(pickup_latitude="", pickup_longitude=""))
    for _ in range(3):  add("origin_coord",      lambda r: r.update(pickup_latitude=0.0, pickup_longitude=0.0))
    for _ in range(4):  add("same_point",        lambda r: r.update(dropoff_latitude=r["pickup_latitude"],
                                                                   dropoff_longitude=r["pickup_longitude"]))
    for _ in range(3):  add("duration_mismatch", lambda r: r.update(trip_duration=r["trip_duration"] + 900))
    for _ in range(2):  add("extreme_duration",  lambda r: set_ts(r, BASE + timedelta(days=9), 72000))

    # Duplicates reference an existing clean row, so the pair is genuinely a duplicate id.
    victim = dict(rows[0])
    for _ in range(2):
        d = dict(victim); d["_defect"] = "dup_exact"; rows.append(d); expected["dup_exact"] += 1
    d = dict(victim); d["_defect"] = "dup_conflicting"
    d["passenger_count"] = 6; d["trip_duration"] = victim["trip_duration"] + 1234
    rows.append(d); expected["dup_conflicting"] += 1

    rng.shuffle(rows)
    return rows, expected


def main():
    ap = argparse.ArgumentParser(description="Generate a synthetic taxi CSV with planted defects.")
    ap.add_argument("--out", default="data/fixture_trips.csv")
    ap.add_argument("--clean", type=int, default=400, help="clean rows (default 400)")
    ap.add_argument("--seed", type=int, default=20260827)
    a = ap.parse_args()

    rows, expected = build(a.clean, a.seed)
    cols = ["id", "vendor_id", "pickup_datetime", "dropoff_datetime", "passenger_count",
            "pickup_longitude", "pickup_latitude", "dropoff_longitude", "dropoff_latitude",
            "store_and_fwd_flag", "trip_duration"]
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"{out}  rows={len(rows)}  clean={a.clean}  sha256={digest[:16]}…")
    print("planted defects:")
    for k, c in sorted(expected.items()):
        rule, action = PLANTED[k]
        print(f"  {c:3}  {k:<18} {rule:<12} expect={action}")


if __name__ == "__main__":
    main()
