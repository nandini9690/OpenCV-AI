"""
SentryLoop approval UI (Streamlit).

The agent auto-routes grade A -> Packer 1 and grade B -> Packer 2.
Every REJECT waits here until a person clicks "Approve recycle" or "Override to B".

Two data sources:
  * Local  - reads outputs/decisions.json + outputs/inspection.json (after running the quick start)
  * S3     - reads results/*.json written by the Lambda; the source image is fetched from S3
             and the defect boxes are drawn with OpenCV

Human decisions are saved next to the data: outputs/approvals.json locally,
or approvals/<tile>.json in the S3 bucket.

Run:
  streamlit run ui/app.py                                   # local
  streamlit run ui/app.py -- --bucket <your-bucket-name>    # S3 (uses your AWS CLI credentials)
"""
import argparse
import collections
import datetime as dt
import json
import os
import sys

import cv2
import numpy as np
import streamlit as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "outputs")
GRADE_COLOURS = {"A": "#21a366", "B": "#e3a008", "REJECT": "#e02424"}


def cli_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default=os.environ.get("TILEQC_BUCKET", ""))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args, _ = ap.parse_known_args(sys.argv[1:])
    return args


# ---------------------------------------------------------------- data sources
def load_local():
    path = os.path.join(OUT, "decisions.json")
    if not os.path.exists(path):
        return None, []
    data = json.load(open(path))
    inspections = {}
    ipath = os.path.join(OUT, "inspection.json")
    if os.path.exists(ipath):
        raw = json.load(open(ipath))
        raw = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
        inspections = {r["image"]: r for r in raw}
    rows = []
    for d in data["decisions"]:
        rows.append({"id": d["image"], "decision": d, "inspection": inspections.get(d["image"]), "source": None})
    return data.get("shift_note"), rows


@st.cache_resource
def s3_client(region):
    import boto3
    return boto3.client("s3", region_name=region)


def load_s3(bucket, region):
    s3 = s3_client(region)
    rows = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="results/"):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".json"):
                continue
            body = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
            name = os.path.splitext(os.path.basename(obj["Key"]))[0]
            rows.append({"id": name, "decision": body["decision"], "inspection": body.get("inspection"),
                         "source": body.get("source"), "modified": obj["LastModified"]})
    rows.sort(key=lambda r: r.get("modified"), reverse=True)
    counts = collections.Counter(r["decision"]["grade"] for r in rows)
    note = f"{len(rows)} tiles inspected: {counts.get('A', 0)} A, {counts.get('B', 0)} B, {counts.get('REJECT', 0)} reject."
    return note, rows


# ---------------------------------------------------------------- approvals
def load_approvals(bucket, region):
    if not bucket:
        path = os.path.join(OUT, "approvals.json")
        return json.load(open(path)) if os.path.exists(path) else {}
    s3, out = s3_client(region), {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="approvals/"):
        for obj in page.get("Contents", []):
            rec = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
            out[rec["id"]] = rec
    return out


def save_approval(bucket, region, row, action, reviewer):
    rec = {"id": row["id"], "action": action, "reviewer": reviewer or "supervisor",
           "original_grade": row["decision"]["grade"],
           "final_route": "Recycle" if action == "approve_recycle" else "Packer 2 - second quality",
           "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if bucket:
        s3_client(region).put_object(Bucket=bucket, Key=f"approvals/{row['id']}.json",
                                     ContentType="application/json", Body=json.dumps(rec, indent=2))
    else:
        path = os.path.join(OUT, "approvals.json")
        allrec = json.load(open(path)) if os.path.exists(path) else {}
        allrec[row["id"]] = rec
        json.dump(allrec, open(path, "w"), indent=2)


# ---------------------------------------------------------------- images
def overlay_for(row, bucket, region):
    """Return an RGB image with defect boxes, or None."""
    local = os.path.join(OUT, f"overlay_{os.path.splitext(row['id'])[0]}.jpg")
    if not bucket and os.path.exists(local):
        return cv2.cvtColor(cv2.imread(local), cv2.COLOR_BGR2RGB)
    if not (bucket and row.get("source")):
        return None
    raw = s3_client(region).get_object(Bucket=bucket, Key=row["source"])["Body"].read()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    for d in (row.get("inspection") or {}).get("defects", []):
        x, y, w, h = d["bbox"]
        cv2.rectangle(img, (x, y), (x + w, y + h), (36, 36, 224), 3)
        cv2.putText(img, d["type"], (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (36, 36, 224), 2)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------- page
def main():
    args = cli_args()
    st.set_page_config(page_title="SentryLoop - Approval", page_icon="🧱", layout="wide")
    st.title("SentryLoop · Reject approval")
    st.caption("The agent routes A → Packer 1 and B → Packer 2 automatically. "
               "Every REJECT waits here for a person before it goes to Recycle.")

    with st.sidebar:
        st.header("Data source")
        bucket = st.text_input("S3 bucket (blank = local outputs/)", value=args.bucket).strip()
        region = st.text_input("AWS region", value=args.region).strip()
        reviewer = st.text_input("Your name", value="")
        if st.button("Refresh"):
            st.rerun()

    try:
        note, rows = load_s3(bucket, region) if bucket else load_local()
        approvals = load_approvals(bucket, region)
    except Exception as e:  # credentials, bucket name, network
        st.error(f"Could not load data: {e}")
        return

    if not rows:
        st.info("No results yet. Run the quick start (local) or upload a tile to s3://<bucket>/incoming/.")
        return

    counts = collections.Counter(r["decision"]["grade"] for r in rows)
    waiting = [r for r in rows if r["decision"]["grade"] == "REJECT" and r["id"] not in approvals]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("A → Packer 1", counts.get("A", 0))
    c2.metric("B → Packer 2", counts.get("B", 0))
    c3.metric("REJECT", counts.get("REJECT", 0))
    c4.metric("Waiting for you", len(waiting))
    if note:
        st.info(note)

    tab_wait, tab_done, tab_all = st.tabs([f"Waiting ({len(waiting)})", f"Reviewed ({len(approvals)})", f"All tiles ({len(rows)})"])

    with tab_wait:
        if not waiting:
            st.success("Nothing waiting. Every reject has been reviewed.")
        for r in waiting:
            d = r["decision"]
            with st.container(border=True):
                left, right = st.columns([2, 3])
                img = overlay_for(r, bucket, region)
                if img is not None:
                    left.image(img, width='stretch')
                else:
                    left.write("(no image available)")
                right.subheader(r["id"])
                right.markdown(f"**Grade:** :red[REJECT] · **Defects:** {', '.join(d['defect_types']) or 'none'}")
                right.write(d.get("summary", ""))
                b1, b2 = right.columns(2)
                if b1.button("✅ Approve recycle", key=f"ok-{r['id']}", type="primary"):
                    save_approval(bucket, region, r, "approve_recycle", reviewer)
                    st.rerun()
                if b2.button("↩️ Override to B", key=f"ov-{r['id']}"):
                    save_approval(bucket, region, r, "override_to_B", reviewer)
                    st.rerun()

    with tab_done:
        if approvals:
            st.dataframe([{"tile": a["id"], "decision": a["action"], "final route": a["final_route"],
                           "by": a["reviewer"], "at": a["at"]} for a in approvals.values()],
                         width='stretch', hide_index=True)
        else:
            st.write("No reviews yet.")

    with tab_all:
        st.dataframe([{"tile": r["id"], "grade": r["decision"]["grade"],
                       "defects": ", ".join(r["decision"]["defect_types"]),
                       "route": r["decision"]["line"], "status": approvals.get(r["id"], {}).get("action", r["decision"]["status"])}
                      for r in rows], width='stretch', hide_index=True)


if __name__ == "__main__":
    main()
