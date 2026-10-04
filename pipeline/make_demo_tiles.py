"""
Generate PUBLIC synthetic demo tiles (slate-style relief, grazing-light look).

  - N "golden" reference tiles (no defects)  -> samples/demo/reference/
  - M test tiles, some with defects           -> samples/demo/test/  + labels.csv

Defect types: crack, chip, spot, stain. Every tile has its own random texture,
just like real slate-effect tiles, so the inspector cannot rely on pixel-matching.

Usage: python pipeline/make_demo_tiles.py --refs 20 --tests 40
"""
import argparse, csv, os, random
import cv2
import numpy as np

W, H = 1200, 600          # tile size in pixels
PAD = 60                  # dark conveyor background around the tile


def slate_texture(rng):
    h = np.zeros((H, W), np.float32)
    for scale, amp in [(4, 1.0), (16, 0.6), (48, 0.35), (160, 0.2)]:
        n = rng.standard_normal((H // scale + 2, W // scale + 2)).astype(np.float32)
        n = cv2.resize(n, (W, H), interpolation=cv2.INTER_CUBIC)
        h += amp * n
    # directional "swirl" strata typical of slate effect
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    phase = rng.uniform(0, 6.28)
    h += 0.5 * np.sin((xx * 0.012 + yy * 0.02) + 2.0 * np.sin(xx * 0.004 + phase))
    return h


def shade(height):
    # grazing light from the left: brightness ~ d(height)/dx
    gx = cv2.Sobel(height, cv2.CV_32F, 1, 0, ksize=3)
    img = 128 + 9 * gx / (gx.std() + 1e-6)          # gentle relief, like a real grazing-light camera
    return np.clip(img, 0, 255)


def add_crack(img, rng):
    x, y = rng.integers(150, W - 150), rng.integers(80, H - 80)
    pts = [(x, y)]
    ang = rng.uniform(0, np.pi)
    for _ in range(rng.integers(8, 16)):
        ang += rng.uniform(-0.5, 0.5)
        x = int(np.clip(x + 18 * np.cos(ang), 5, W - 5)); y = int(np.clip(y + 18 * np.sin(ang), 5, H - 5))
        pts.append((x, y))
    cv2.polylines(img, [np.array(pts, np.int32)], False, 40, 2, cv2.LINE_AA)
    xs, ys = zip(*pts)
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def add_chip(img, rng):
    corner = rng.integers(0, 4)
    cx = 0 if corner in (0, 3) else W; cy = 0 if corner in (0, 1) else H
    r = rng.integers(25, 55)
    poly = np.array([(cx, cy), (abs(cx - r), cy), (cx, abs(cy - int(r * 0.8)))], np.int32)
    cv2.fillPoly(img, [poly], 15)
    x, y, w, h = cv2.boundingRect(poly)
    return [x, y, w, h]


def add_spot(img, rng):
    x, y, r = rng.integers(60, W - 60), rng.integers(60, H - 60), rng.integers(4, 9)
    cv2.circle(img, (int(x), int(y)), int(r), int(rng.choice([25, 235])), -1, cv2.LINE_AA)
    return [int(x - r), int(y - r), int(2 * r), int(2 * r)]


def add_stain(img, rng):
    x, y = rng.integers(150, W - 150), rng.integers(100, H - 100)
    a, b = rng.integers(40, 90), rng.integers(25, 60)
    m = np.zeros_like(img, np.float32)
    cv2.ellipse(m, (int(x), int(y)), (int(a), int(b)), rng.uniform(0, 180), 0, 360, 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), 12)
    img[:] = np.clip(img - 35 * m, 0, 255)
    return [int(x - a), int(y - b), int(2 * a), int(2 * b)]


DEFECTS = {"crack": add_crack, "chip": add_chip, "spot": add_spot, "stain": add_stain}


def make_tile(rng, defect=None):
    tile = shade(slate_texture(rng)).astype(np.float32)
    tile += rng.normal(0, 2, tile.shape)                         # sensor noise
    tile += rng.uniform(-6, 6)                                   # small lighting drift
    box = DEFECTS[defect](tile, rng) if defect else None
    canvas = np.full((H + 2 * PAD, W + 2 * PAD), 12, np.float32)
    canvas[PAD:PAD + H, PAD:PAD + W] = tile
    # small placement jitter on the conveyor
    M = cv2.getRotationMatrix2D((canvas.shape[1] / 2, canvas.shape[0] / 2), rng.uniform(-1.2, 1.2), 1.0)
    M[:, 2] += rng.uniform(-15, 15, 2)
    canvas = cv2.warpAffine(canvas, M, (canvas.shape[1], canvas.shape[0]), borderValue=12)
    return np.clip(canvas, 0, 255).astype(np.uint8), box


def main(out, n_ref, n_test, seed):
    rng = np.random.default_rng(seed)
    os.makedirs(f"{out}/reference", exist_ok=True); os.makedirs(f"{out}/test", exist_ok=True)
    for i in range(n_ref):
        cv2.imwrite(f"{out}/reference/ref_{i:02d}.jpg", make_tile(rng)[0])
    kinds = [None] * (n_test // 2) + [list(DEFECTS)[i % 4] for i in range(n_test - n_test // 2)]
    random.Random(seed).shuffle(kinds)
    with open(f"{out}/test/labels.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["file", "defect"])
        for i, k in enumerate(kinds):
            img, _ = make_tile(rng, k)
            name = f"tile_{i:03d}.jpg"; cv2.imwrite(f"{out}/test/{name}", img); w.writerow([name, k or "none"])
    print(f"{n_ref} reference + {n_test} test tiles -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="samples/demo"); ap.add_argument("--refs", type=int, default=20)
    ap.add_argument("--tests", type=int, default=40); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(); main(a.out, a.refs, a.tests, a.seed)
