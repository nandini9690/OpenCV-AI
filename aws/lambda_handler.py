"""
AWS Lambda entry point.
Trigger: a tile image uploaded to s3://<bucket>/incoming/
Result:  inspection + decision written to s3://<bucket>/results/<name>.json

The golden reference (models/reference.json) is built once from ~20 good tiles
and packaged with the function (or loaded from S3 via REFERENCE_KEY).
Deploy as a container image (OpenCV is large) - see aws/template.yaml.
"""
import json, os, sys, tempfile
import boto3

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from pipeline.tile_qc import inspect     # noqa: E402
from agent.decide import decide          # noqa: E402

s3 = boto3.client("s3")


def load_reference(bucket):
    key = os.environ.get("REFERENCE_KEY")
    if key:
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    return json.load(open(os.environ.get("REFERENCE_PATH", "models/reference.json")))


def handler(event, context):
    rec = event["Records"][0]["s3"]
    bucket, key = rec["bucket"]["name"], rec["object"]["key"]
    ref = load_reference(bucket)
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, os.path.basename(key))
        s3.download_file(bucket, key, local)
        result = inspect(local, ref)
    decision = decide([result])[0]
    name = os.path.splitext(os.path.basename(key))[0]
    s3.put_object(Bucket=bucket, Key=f"results/{name}.json", ContentType="application/json",
                  Body=json.dumps({"source": key, "inspection": result, "decision": decision}, indent=2))
    return {"statusCode": 200, "grade": result["grade"], "status": decision["status"]}
