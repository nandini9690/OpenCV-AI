"""
AWS Lambda entry point.
Trigger: a video/frame uploaded to s3://<bucket>/incoming/
Result:  events + decisions written to s3://<bucket>/results/<name>.json

Packaging note: OpenCV is large; deploy this Lambda as a container image (see template.yaml)
or attach an OpenCV Lambda layer.
"""
import json, os, sys, tempfile
import boto3

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from pipeline.detect import run          # noqa: E402
from agent.decide import decide           # noqa: E402

s3 = boto3.client("s3")
ZONES = os.environ.get("ZONES_PATH", "pipeline/zones.json")


def handler(event, context):
    rec = event["Records"][0]["s3"]
    bucket, key = rec["bucket"]["name"], rec["object"]["key"]
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, os.path.basename(key))
        s3.download_file(bucket, key, local)
        events = run(local, ZONES, os.path.join(tmp, "events.json"), preview=False)
        decisions = decide(events)
    name = os.path.splitext(os.path.basename(key))[0]
    body = json.dumps({"source": key, "events": events, "decisions": decisions}, indent=2)
    s3.put_object(Bucket=bucket, Key=f"results/{name}.json", Body=body, ContentType="application/json")
    return {"statusCode": 200, "events": len(events), "decisions": len(decisions)}
