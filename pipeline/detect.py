"""
Site Safety Monitor - vision pipeline (Team Cloud Catalyst, OpenCV AI Competition 2026)

Stage 1 (works today, no model needed):
  - Background subtraction (MOG2) finds moving people/objects.
  - Each moving blob is checked against restricted-zone polygons from zones.json.

Stage 2 (plug in when ready):
  - Load a YOLO-style ONNX model with cv2.dnn for "person / helmet / vest".
  - Set PPE_MODEL=path/to/model.onnx and the PPE check switches on automatically.

Output: a list of events (JSON) that the agent in agent/decide.py turns into decisions.

Usage:
  python pipeline/detect.py --video samples/site.mp4 --zones pipeline/zones.json --out outputs/events.json --preview
"""
import argparse, json, os, time
import cv2
import numpy as np


def load_zones(path, w, h):
    cfg = json.load(open(path))
    zones = []
    for z in cfg["restricted_zones"]:
        pts = np.array([[int(x * w), int(y * h)] for x, y in z["polygon"]], np.int32)
        zones.append({"name": z["name"], "pts": pts})
    return cfg, zones


def in_zone(point, zone_pts):
    return cv2.pointPolygonTest(zone_pts, point, False) >= 0


class PPEModel:
    """Optional ONNX detector. Expects YOLO-style output [1, N, 5+classes]."""
    CLASSES = ["person", "helmet", "vest"]

    def __init__(self, path, conf=0.4):
        self.net = cv2.dnn.readNetFromONNX(path)
        self.conf = conf

    def detect(self, frame):
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (640, 640), swapRB=True)
        self.net.setInput(blob)
        out = self.net.forward()[0]
        dets = []
        for row in out:
            scores = row[5:]
            cid = int(np.argmax(scores))
            score = float(row[4] * scores[cid])
            if score < self.conf or cid >= len(self.CLASSES):
                continue
            cx, cy, bw, bh = row[:4]
            x = int((cx - bw / 2) * w / 640); y = int((cy - bh / 2) * h / 640)
            dets.append({"label": self.CLASSES[cid], "score": round(score, 3),
                         "box": [x, y, int(bw * w / 640), int(bh * h / 640)]})
        return dets


def run(video, zones_path, out_path, preview=False, max_frames=None):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cfg, zones = load_zones(zones_path, w, h)
    min_area = cfg.get("min_person_area", 0.01) * w * h
    cooldown = cfg.get("alert_cooldown_s", 10)

    bg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=True)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    ppe = PPEModel(os.environ["PPE_MODEL"]) if os.environ.get("PPE_MODEL") else None

    events, last_alert, idx = [], {}, 0
    while True:
        ok, frame = cap.read()
        if not ok or (max_frames and idx >= max_frames):
            break
        t = idx / fps
        mask = bg.apply(frame)
        mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)[1]           # drop shadows
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours:
            if cv2.contourArea(c) < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            foot = (x + bw // 2, y + bh)                                     # feet position
            for z in zones:
                if in_zone(foot, z["pts"]) and t - last_alert.get(z["name"], -1e9) >= cooldown:
                    last_alert[z["name"]] = t
                    events.append({"type": "zone_intrusion", "zone": z["name"], "t": round(t, 2),
                                   "frame": idx, "box": [x, y, bw, bh], "camera": cfg["camera_id"]})
            if preview:
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 200, 255), 2)

        if ppe and idx % int(fps) == 0:                                      # 1 PPE check per second
            dets = ppe.detect(frame)
            people = [d for d in dets if d["label"] == "person"]
            helmets = [d for d in dets if d["label"] == "helmet"]
            if len(people) > len(helmets):
                events.append({"type": "ppe_missing", "item": "helmet", "t": round(t, 2),
                               "frame": idx, "people": len(people), "camera": cfg["camera_id"]})

        if preview:
            for z in zones:
                cv2.polylines(frame, [z["pts"]], True, (0, 0, 255), 2)
            cv2.imshow("Site Safety Monitor", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
        idx += 1

    cap.release()
    if preview:
        cv2.destroyAllWindows()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    json.dump({"video": os.path.basename(video), "frames": idx, "events": events}, open(out_path, "w"), indent=2)
    print(f"{idx} frames, {len(events)} events -> {out_path}")
    return events


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--zones", default="pipeline/zones.json")
    ap.add_argument("--out", default="outputs/events.json")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--max-frames", type=int)
    a = ap.parse_args()
    run(a.video, a.zones, a.out, a.preview, a.max_frames)
