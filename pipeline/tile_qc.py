"""
Tile QC - golden-reference inspection (Team Cloud Catalyst, OpenCV AI Competition 2026)

Idea: run ~20 of the best tiles through the camera, learn what "good" looks like,
then inspect every new tile against that reference and grade it.

Works for random-texture tiles (slate, stone effect) because it does NOT pixel-match:
it learns the normal *statistics* of the surface and flags anything outside them.

  1. find the tile on the conveyor and straighten it (contour + perspective warp)
  2. remove lighting gradient (high-pass)
  3. defect maps: dark / bright deviations (cracks, pits, spots), edge holes (chips),
     patch brightness (stains / shade)
  4. thresholds learned from the reference tiles (high percentiles)
  5. connected components -> defects -> type, size, position
  6. grade A / B / REJECT  (agent/decide.py routes them)

Usage:
  python pipeline/tile_qc.py build   --refs samples/demo/reference --out models/reference.json
  python pipeline/tile_qc.py inspect --ref models/reference.json --image samples/demo/test/tile_000.jpg
  python pipeline/tile_qc.py eval    --ref models/reference.json --test samples/demo/test
"""
import argparse, csv, glob, json, os
import cv2
import numpy as np

SIZE = (1200, 600)        # normalised tile size (w, h)
EDGE = 18                 # px band treated as "edge" (chips)
PATCH = 50                # patch size for stain / shade check


# ---------- 1-2. locate, straighten, normalise ----------
def load_gray(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise SystemExit(f"Cannot read {path}")
    return img


def find_tile(gray):
    """Return the tile warped to SIZE. Falls back to a plain resize if no clear tile outline."""
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        c = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(c) > 0.3 * gray.size:
            box = cv2.boxPoints(cv2.minAreaRect(c)).astype(np.float32)
            s, d = box.sum(1), np.diff(box, axis=1).ravel()
            src = np.array([box[s.argmin()], box[d.argmin()], box[s.argmax()], box[d.argmax()]], np.float32)
            w, h = SIZE
            dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32)
            return cv2.warpPerspective(gray, cv2.getPerspectiveTransform(src, dst), SIZE)
    return cv2.resize(gray, SIZE)


def maps(tile):
    t = tile.astype(np.float32)
    hp = t - cv2.GaussianBlur(t, (0, 0), 25)                     # remove lighting gradient
    hp = cv2.GaussianBlur(hp, (0, 0), 1.5)                       # suppress single-pixel texture noise
    dark = np.maximum(-hp, 0)                                    # cracks, pits, dark spots
    bright = np.maximum(hp, 0)                                   # bright spots, glaze drops
    patches = cv2.resize(cv2.GaussianBlur(t, (0, 0), 6), (SIZE[0] // PATCH, SIZE[1] // PATCH),
                         interpolation=cv2.INTER_AREA)          # local brightness (stains)
    return dark, bright, patches


def chips(tile, ref):
    """Missing material at the tile edge shows up as conveyor-dark pixels inside the tile outline."""
    hole = (tile < ref["chip_level"]).astype(np.uint8)
    hole[4:-4, 4:-4][EDGE * 3:-EDGE * 3, EDGE * 3:-EDGE * 3] = 0      # only look near the edges
    hole[:3, :] = hole[-3:, :] = 0; hole[:, :3] = hole[:, -3:] = 0    # ignore warp border
    n, _, st, _ = cv2.connectedComponentsWithStats(hole)
    return [{"type": "chip", "bbox": [int(x), int(y), int(w), int(h)], "area_px": int(a)}
            for x, y, w, h, a in st[1:] if a >= 150]


def inner(a):
    return a[EDGE:-EDGE, EDGE:-EDGE]


# ---------- 3-4. learn the reference ----------
def build(ref_dir, out):
    files = sorted(glob.glob(os.path.join(ref_dir, "*.jpg")) + glob.glob(os.path.join(ref_dir, "*.png")))
    if len(files) < 5:
        raise SystemExit("Need at least 5 reference tiles (20 recommended).")
    d_all, b_all, p_dev, means = [], [], [], []
    for f in files:
        tile = find_tile(load_gray(f))
        d, b, p = maps(tile)
        d_all.append(inner(d).ravel()); b_all.append(inner(b).ravel())
        p_dev.append((p - np.median(p)).ravel()); means.append(float(inner(tile).mean()))
    d_all, b_all, p_dev = map(np.concatenate, (d_all, b_all, p_dev))
    ref = {
        "n_reference": len(files),
        "dark_thr": float(np.percentile(d_all, 99.999) * 1.2),
        "bright_thr": float(np.percentile(b_all, 99.999) * 1.2),
        "chip_level": float(np.mean(means) * 0.22),
        "stain_thr": float(np.percentile(np.abs(p_dev), 99.9) * 1.5),
        "shade_mean": float(np.mean(means)), "shade_std": float(np.std(means) + 1e-6),
        "min_area": 20,
    }
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(ref, open(out, "w"), indent=2)
    print(f"Reference learned from {len(files)} tiles -> {out}")
    return ref


# ---------- 5-6. inspect + grade ----------
def classify(x, y, w, h, area, kind_hint):
    long_side = max(w, h)
    fill = area / float(max(1, w * h))          # thin, wandering shapes fill little of their box
    if long_side >= 40 and fill < 0.35:
        return "crack"
    return "spot"


def inspect(path, ref, save_overlay=None):
    tile = find_tile(load_gray(path))
    d, b, p = maps(tile)
    defects = []
    defects += chips(tile, ref)
    for name, m, thr in (("dark", d, ref["dark_thr"]), ("bright", b, ref["bright_thr"])):
        m = m.copy(); m[:EDGE, :] = m[-EDGE:, :] = 0; m[:, :EDGE] = m[:, -EDGE:] = 0
        mask = (m > thr).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))   # join broken crack segments
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        for x, y, w, h, area in stats[1:]:
            if area >= ref["min_area"]:
                defects.append({"type": classify(x, y, w, h, area, name), "bbox": [int(x), int(y), int(w), int(h)],
                                "area_px": int(area)})
    dev = np.abs(p - np.median(p))
    ys, xs = np.where(dev > ref["stain_thr"])
    if len(xs) >= 2 and not any(k["type"] in ("crack", "chip") for k in defects):   # cracks also darken patches
        defects.append({"type": "stain", "bbox": [int(xs.min() * PATCH), int(ys.min() * PATCH),
                        int((np.ptp(xs) + 1) * PATCH), int((np.ptp(ys) + 1) * PATCH)], "area_px": int(len(xs) * PATCH * PATCH)})
    shade_z = (float(inner(tile).mean()) - ref["shade_mean"]) / ref["shade_std"]

    kinds = {k["type"] for k in defects}
    if kinds & {"crack", "chip"}:
        grade = "REJECT"
    elif "stain" in kinds or len(defects) > 3 or abs(shade_z) > 6:
        grade = "B"
    elif defects:
        grade = "B" if any(k["area_px"] > 120 for k in defects) else "A"
    else:
        grade = "A"
    result = {"image": os.path.basename(path), "grade": grade, "defects": defects, "shade_z": round(shade_z, 2)}

    if save_overlay:
        vis = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
        col = {"crack": (0, 0, 255), "chip": (0, 140, 255), "spot": (0, 255, 255), "stain": (255, 0, 255)}
        for k in defects:
            x, y, w, h = k["bbox"]
            cv2.rectangle(vis, (x - 4, y - 4), (x + w + 4, y + h + 4), col[k["type"]], 2)
            cv2.putText(vis, k["type"], (x, max(14, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col[k["type"]], 1)
        cv2.putText(vis, f"GRADE {grade}", (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.imwrite(save_overlay, vis)
    return result


def evaluate(ref, test_dir, out_dir="outputs"):
    os.makedirs(out_dir, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(test_dir, "labels.csv"))))
    results, tp, fp, fn, tn = [], 0, 0, 0, 0
    for r in rows:
        res = inspect(os.path.join(test_dir, r["file"]), ref, os.path.join(out_dir, "overlay_" + r["file"]))
        res["truth"] = r["defect"]; results.append(res)
        bad_truth, bad_pred = r["defect"] != "none", bool(res["defects"])
        tp += bad_truth and bad_pred; fn += bad_truth and not bad_pred
        fp += (not bad_truth) and bad_pred; tn += (not bad_truth) and not bad_pred
    prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)
    summary = {"tiles": len(rows), "TP": tp, "FP": fp, "FN": fn, "TN": tn,
               "precision": round(prec, 3), "recall": round(rec, 3)}
    json.dump({"summary": summary, "results": results}, open(os.path.join(out_dir, "inspection.json"), "w"), indent=2)
    print(json.dumps(summary))
    for r in results:
        flag = "" if (r["truth"] != "none") == bool(r["defects"]) else "   <-- miss"
        print(f'{r["image"]}  truth={r["truth"]:6s} grade={r["grade"]:6s} found={[d["type"] for d in r["defects"]]}{flag}')
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--refs", required=True); b.add_argument("--out", default="models/reference.json")
    i = sub.add_parser("inspect"); i.add_argument("--ref", required=True); i.add_argument("--image", required=True)
    i.add_argument("--overlay")
    e = sub.add_parser("eval"); e.add_argument("--ref", required=True); e.add_argument("--test", required=True)
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.refs, a.out)
    elif a.cmd == "inspect":
        print(json.dumps(inspect(a.image, json.load(open(a.ref)), a.overlay), indent=2))
    else:
        evaluate(json.load(open(a.ref)), a.test)
