# AWS setup checklist (owner: Edmund) — target Oct 5–12

## 0. Safety first (10 min)
- [ ] Sign in as root once → enable **MFA** on root → create an **IAM user/Identity Center user** for daily work
- [ ] **Billing → Budgets → Create budget**: monthly cost budget **USD 10**, email alert at 50% and 100%
- [ ] Pick one region and stick to it (e.g. `us-east-1` for widest Bedrock model access)

## 1. Local tools (15 min)
- [ ] AWS CLI v2 → `aws configure` (use the IAM user's keys, never root)
- [ ] AWS SAM CLI + Docker Desktop
- [ ] `python -m venv .venv && pip install -r requirements.txt`

## 2. Run locally first
```bash
python pipeline/make_demo_tiles.py
python pipeline/tile_qc.py build --refs samples/demo/reference
python pipeline/tile_qc.py eval --ref models/reference.json --test samples/demo/test
python agent/decide.py
```

## 3. Deploy (container Lambda + S3 trigger)
```bash
sam build -t aws/template.yaml
sam deploy --guided          # set BucketName to something globally unique
```
Before `sam build`, run the `build` step so `models/reference.json` exists.
Test: upload a tile image to `s3://<bucket>/incoming/` → result appears in `results/`.

## 4. Optional: Bedrock summaries
- [ ] Bedrock console → **Model access** → enable one small text model
- [ ] Set `USE_BEDROCK=1` and `BEDROCK_MODEL=<model id>` on the Lambda

## Cost guardrails
- Lambda + S3 at demo scale ≈ cents. Biggest risk = forgetting resources running.
- No EC2/GPU instances unless agreed. Delete the stack after judging: `sam delete`.
