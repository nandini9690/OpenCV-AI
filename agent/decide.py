"""
Tile QC agent - turns inspection results into line actions, with a human approval gate.

  grade A       -> Packer 1 (first quality)            auto
  grade B       -> Packer 2 (second quality / commercial) auto
  grade REJECT  -> Recycle bin (crushed back into body mix)  WAITS FOR HUMAN APPROVAL

Rules are deterministic (explainable for judges). An optional LLM step (Amazon Bedrock)
writes the plain-English shift note; it never makes the decision.

Usage:
  python agent/decide.py --inspection outputs/inspection.json --out outputs/decisions.json
  USE_BEDROCK=1 BEDROCK_MODEL=<model-id> python agent/decide.py ...
"""
import argparse, collections, json, os

ROUTES = {
    "A":      {"action": "route_to_packer_1", "line": "Packer 1 - first quality", "human_gate": False},
    "B":      {"action": "route_to_packer_2", "line": "Packer 2 - second quality", "human_gate": False},
    "REJECT": {"action": "divert_to_recycle", "line": "Recycle", "human_gate": True},
}


def explain(result, route):
    found = ", ".join(sorted({d["type"] for d in result["defects"]})) or "no defects"
    return f'{result["image"]}: grade {result["grade"]} ({found}) -> {route["line"]}.'


def shift_note(decisions):
    counts = collections.Counter(d["grade"] for d in decisions)
    defects = collections.Counter(t for d in decisions for t in d["defect_types"])
    base = (f"{len(decisions)} tiles inspected: {counts.get('A', 0)} A, {counts.get('B', 0)} B, "
            f"{counts.get('REJECT', 0)} reject. Defects seen: {dict(defects) or 'none'}.")
    if not os.environ.get("USE_BEDROCK"):
        return base
    import boto3
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = client.converse(
        modelId=os.environ["BEDROCK_MODEL"],
        messages=[{"role": "user", "content": [{"text":
            "Write a 3-sentence end-of-shift quality note for a tile factory supervisor. "
            "Mention the most common defect and one thing to check on the line. Facts: " + base}]}],
        inferenceConfig={"maxTokens": 160, "temperature": 0.2})
    return resp["output"]["message"]["content"][0]["text"].strip()


def decide(results):
    out = []
    for r in results:
        route = ROUTES[r["grade"]]
        out.append({
            "image": r["image"], "grade": r["grade"],
            "defect_types": sorted({d["type"] for d in r["defects"]}),
            **route,
            "status": "awaiting_approval" if route["human_gate"] else "auto_executed",
            "summary": explain(r, route),
        })
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspection", default="outputs/inspection.json")
    ap.add_argument("--out", default="outputs/decisions.json")
    a = ap.parse_args()
    data = json.load(open(a.inspection))
    results = data["results"] if isinstance(data, dict) and "results" in data else data
    decisions = decide(results)
    json.dump({"shift_note": shift_note(decisions), "decisions": decisions}, open(a.out, "w"), indent=2)
    gated = sum(d["status"] == "awaiting_approval" for d in decisions)
    print(f"{len(decisions)} decisions ({gated} rejects waiting for human approval) -> {a.out}")
