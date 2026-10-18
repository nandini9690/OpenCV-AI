"""
Private real-image sanity check  -  LOCAL ONLY, never uploaded.

Put a few real tile photos in samples/private/ (git-ignored) and name each file by what is
really on it, e.g.  good_01.jpg, crack_01.jpg, chip_01.jpg, spot_01.jpg, stain_01.jpg.
The script inspects them with the same reference and reports how the grades compare.

Results go to outputs/private/ (git-ignored). Only the summary numbers - never the images -
should be quoted in the report, and only with the image owner's permission (docs/DATA.md).

Usage:
  python eval/real_check.py --ref models/reference.json --dir samples/private
"""
import argparse
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pipeline.tile_qc import inspect  # noqa: E402

EXPECTED = {"good": "A", "spot": "B", "stain": "B", "crack": "REJECT", "chip": "REJECT"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="models/reference.json")
    ap.add_argument("--dir", default="samples/private")
    ap.add_argument("--out", default="outputs/private")
    a = ap.parse_args()

    files = sorted(f for ext in ("jpg", "jpeg", "png") for f in glob.glob(os.path.join(a.dir, f"*.{ext}")))
    if not files:
        raise SystemExit(f"No images in {a.dir}. Add a few real photos named good_*/crack_*/chip_*/spot_*/stain_*.")
    os.makedirs(a.out, exist_ok=True)
    ref = json.load(open(a.ref))

    rows, agree = [], 0
    for f in files:
        name = os.path.basename(f)
        label = name.split("_")[0].lower()
        expected = EXPECTED.get(label, "?")
        r = inspect(f, ref, save_overlay=os.path.join(a.out, f"overlay_{name}"))
        ok = expected == r["grade"]
        agree += ok
        found = ", ".join(sorted({d["type"] for d in r["defects"]})) or "-"
        rows.append({"image": name, "label": label, "expected": expected, "grade": r["grade"],
                     "found": found, "match": "yes" if ok else "NO"})
        print(f"{name:28s} label={label:6s} expected={expected:6s} got={r['grade']:6s} found={found}")

    with open(os.path.join(a.out, "real_check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\n{agree}/{len(rows)} real images graded as expected -> {a.out}/real_check.csv")


if __name__ == "__main__":
    main()
