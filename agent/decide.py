"""
Safety agent - turns vision events into decisions, with a human approval gate.

Flow:  events.json  ->  score severity  ->  decide action  ->  needs_human? -> queue for approval
Severity rules are deterministic (explainable for judges). An optional LLM step
(Amazon Bedrock) writes the plain-English incident summary; it never decides on its own.

Usage:
  python agent/decide.py --events outputs/events.json --out outputs/decisions.json
  USE_BEDROCK=1 BEDROCK_MODEL=<model-id> python agent/decide.py ...
"""
import argparse, json, os

RULES = {
    "zone_intrusion": {"severity": "high",   "action": "stop_machinery_and_alert_supervisor", "human_gate": True},
    "ppe_missing":    {"severity": "medium", "action": "notify_site_officer",                  "human_gate": False},
}


def summarise(event, decision):
    base = (f"{event['type'].replace('_', ' ').title()} on {event.get('camera')} at t={event['t']}s"
            + (f" in '{event['zone']}'" if event.get("zone") else "")
            + f". Proposed: {decision['action'].replace('_', ' ')}.")
    if not os.environ.get("USE_BEDROCK"):
        return base
    import boto3
    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = client.converse(
        modelId=os.environ["BEDROCK_MODEL"],
        messages=[{"role": "user", "content": [{"text":
            "Write a 2-sentence site-safety incident note for a supervisor. Facts only: " + base}]}],
        inferenceConfig={"maxTokens": 120, "temperature": 0.2})
    return resp["output"]["message"]["content"][0]["text"].strip()


def decide(events):
    out = []
    for e in events:
        rule = RULES.get(e["type"], {"severity": "low", "action": "log_only", "human_gate": False})
        d = {"event": e, **rule, "status": "awaiting_approval" if rule["human_gate"] else "auto_executed"}
        d["summary"] = summarise(e, d)
        out.append(d)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="outputs/events.json")
    ap.add_argument("--out", default="outputs/decisions.json")
    a = ap.parse_args()
    events = json.load(open(a.events))["events"]
    decisions = decide(events)
    json.dump(decisions, open(a.out, "w"), indent=2)
    gated = sum(d["status"] == "awaiting_approval" for d in decisions)
    print(f"{len(decisions)} decisions ({gated} waiting for human approval) -> {a.out}")
