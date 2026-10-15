"""
AWS Lambda entry point.
Triggers:
 1. Tile image uploaded to s3://<bucket>/incoming/
 2. Direct HTTP POST request with image binary/base64 data via Web Endpoint/Function URL
"""
import base64
import json
import os
import sys
import tempfile
import boto3
import base64, json, os, uuid

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from pipeline.tile_qc import inspect     # noqa: E402
from agent.decide import decide          # noqa: E402

s3 = boto3.client("s3")


def load_reference(bucket=None):
    key = os.environ.get("REFERENCE_KEY")
    if key and bucket:
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    return json.load(open(os.environ.get("REFERENCE_PATH", "models/reference.json")))


def s3_handler(event, context):
    # -------------------------------------------------------------
    # CASE 1: S3 Bucket Event Trigger
    # -------------------------------------------------------------
    if "Records" in event:
        rec = event["Records"][0]["s3"]
        bucket, key = rec["bucket"]["name"], rec["object"]["key"]
        ref = load_reference(bucket)
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, os.path.basename(key))
            s3.download_file(bucket, key, local)
            result = inspect(local, ref)
        decision = decide([result])[0]
        name = os.path.splitext(os.path.basename(key))[0]
        s3.put_object(
            Bucket=bucket,
            Key=f"results/{name}.json",
            ContentType="application/json",
            Body=json.dumps({"source": key, "inspection": result, "decision": decision}, indent=2)
        )
        return {"statusCode": 200, "grade": result["grade"], "status": decision["status"]}

    # -------------------------------------------------------------
    # CASE 2: HTTP Web Endpoint Request (curl / Postman)
    # -------------------------------------------------------------
    elif "body" in event:
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            image_bytes = base64.b64decode(body)
        elif isinstance(body, str):
            try:
                image_bytes = base64.b64decode(body)
            except Exception:
                image_bytes = body.encode("utf-8")
        else:
            image_bytes = body

        ref = load_reference()
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, "uploaded_tile.jpg")
            with open(local, "wb") as f:
                f.write(image_bytes)
            result = inspect(local, ref)

        decision = decide([result])[0]
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"inspection": result, "decision": decision}, indent=2)
        }

    return {"statusCode": 400, "body": json.dumps({"error": "Unsupported event format"})}
_s3 = boto3.client("s3")
_BUCKET = os.environ.get("BUCKET_NAME", "cloud-catalyst-tileqc-nc2026")

_PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width">
<title>Tile QC Inspector</title></head>
<body style="font-family:sans-serif;max-width:680px;margin:40px auto;padding:0 16px">
<h1>Tile QC Inspector</h1>
<p>Upload a tile photo. OpenCV 5 on AWS Lambda inspects it.</p>
<input type=file id=f accept="image/*"> <button onclick="go()">Inspect</button>
<pre id=out style="white-space:pre-wrap;background:#f4f4f4;padding:12px"></pre>
<script>
async function go(){const f=document.getElementById('f').files[0];if(!f)return;
const b=await new Promise(r=>{const x=new FileReader();x.onload=()=>r(x.result.split(',')[1]);x.readAsDataURL(f)});
out.textContent='Inspecting...';
const res=await fetch(location.href,{method:'POST',headers:{'content-type':'application/json'},
 body:JSON.stringify({image:b,name:f.name})});
out.textContent=await res.text();}
</script></body></html>"""

def handler(event, context):
    # 1) Normal S3 upload trigger: use the original code
    if "Records" in event:
        return s3_handler(event, context)

    # 2) Someone opened the web link
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    if method == "GET":
        return {"statusCode": 200, "headers": {"content-type": "text/html"}, "body": _PAGE}

    # 3) Photo uploaded from the web page
    try:
        body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode()
        data = json.loads(body)
        ext = os.path.splitext(data.get("name", "tile.jpg"))[1] or ".jpg"
        key = f"web-uploads/{uuid.uuid4().hex}{ext}"
        _s3.put_object(Bucket=_BUCKET, Key=key, Body=base64.b64decode(data["image"]))

        fake_event = {"Records": [{"s3": {"bucket": {"name": _BUCKET}, "object": {"key": key}}}]}
        result = s3_handler(fake_event, context)
        return {"statusCode": 200, "headers": {"content-type": "application/json"},
                "body": json.dumps({"uploaded": key, "result": result}, default=str, indent=2)}
    except Exception as e:
        return {"statusCode": 500, "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": str(e)})}

