# Cloud Catalyst · Tile QC Inspector
**OpenCV AI Competition 2026 (powered by AWS) — Agentic Vision track**
Team: Edmund Anthony · Nandani Chauhan

Ceramic tile factories still rely on people at the end of the kiln line to spot cracks, chips,
spots and stains — and to decide which tiles are first quality, second quality or scrap.
This project teaches a camera what a **good** tile looks like from about **20 of the best tiles**,
then inspects every new tile, **grades it** and lets an AI agent **route it** to the right packer —
with a **human approval gate** before anything is sent to recycling.

## Try it live
**Web endpoint (AWS Lambda Function URL, us-east-1):**
https://hkdbd4v3q4mfndvdjo4kvxzndm0ddjlj.lambda-url.us-east-1.on.aws/

Open it, choose a tile image from `samples/demo/test/` (run `python pipeline/make_demo_tiles.py` first),
click **Inspect**. Checked on the live service (OpenCV `5.0.0`):

| Tile | Grade | Route | Status | Defects |
|---|---|---|---|---|
| `tile_011.jpg` | A | Packer 1 - first quality | auto_executed | none |
| `tile_019.jpg` | REJECT | Recycle | awaiting_approval | crack |
| `tile_037.jpg` | REJECT | Recycle | awaiting_approval | chip, spot |

## How it works
```
20 best tiles ──► learn "good" statistics ──► models/reference.json
                                                    │
tile image ─► S3 incoming/ ─► Lambda: find + straighten tile ─► defect maps ─► defects + grade
                                                    │
                     agent:  A → Packer 1   ·   B → Packer 2   ·   REJECT → Recycle (needs human approval)
                                                    │
                                     approval UI  +  end-of-shift note (Bedrock, optional)
```
**Why statistics, not pixel matching:** slate- and stone-effect tiles have a different random
texture on every piece. The inspector learns the *normal range* of surface relief, brightness and
edges from the reference tiles and flags anything outside it.

| Defect | How it is found | Grade |
|---|---|---|
| Crack | thin, long dark structure after high-pass | REJECT |
| Chip | missing material at the tile edge | REJECT |
| Spot / pinhole | small dark or bright blob | A (tiny) / B |
| Stain / shade patch | local brightness outside reference range | B |

## Results (public synthetic set, OpenCV 5.0.0, Python 3.12)
Defect detection (a tile counts as positive if it has any defect):

| Set | Tiles | Precision | Recall |
|---|---|---|---|
| Demo set (seed 7) | 40 | 1.00 | 1.00 |
| Unseen set (seed 99) | 40 | 1.00 | 0.95 (1 small chip missed) |

Grade agreement (expected grade from the label vs. graded):

| Set | Exact grade | Misses |
|---|---|---|
| Demo set | 39 / 40 | 1 small spot graded A instead of B (tiny spots are allowed in A by design) |
| Unseen set | 37 / 40 | 2 small spots graded A; **1 small edge chip graded A instead of REJECT** |

Speed: about 60 ms per tile on a laptop CPU (inspection only, 1200 × 600 px).
Reproduce: `python pipeline/make_demo_tiles.py --seed 99 --out /tmp/s2` then
`python pipeline/tile_qc.py eval --ref models/reference.json --test /tmp/s2/test`.

## Quick start (local)
Requires **Python 3.12**. Versions are pinned in `requirements.txt` (OpenCV **5.0.0.93**).
```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python pipeline/make_demo_tiles.py                                   # 20 reference + 40 test tiles
python pipeline/tile_qc.py build   --refs samples/demo/reference     # learn "good" -> models/reference.json
python pipeline/tile_qc.py eval    --ref models/reference.json --test samples/demo/test
python agent/decide.py                                               # routes + shift note
```
Overlays with boxes and grades are written to `outputs/`.

## Approval UI
```bash
pip install -r requirements-ui.txt
streamlit run ui/app.py                                    # local results in outputs/
streamlit run ui/app.py -- --bucket <your-bucket-name>     # live results from S3 (uses your AWS CLI credentials)
```
Shows A / B / REJECT counts and a queue of rejects with the defect boxes drawn on the tile.
**Approve recycle** or **Override to B** is saved to `approvals/<tile>.json` in S3 (or `outputs/approvals.json` locally).

## Deploy to AWS (S3 → Lambda + public web endpoint)
Needs AWS CLI v2, SAM CLI and Docker running. Region: `us-east-1`.
```bash
python pipeline/make_demo_tiles.py
python pipeline/tile_qc.py build --refs samples/demo/reference    # creates models/reference.json (copied into the image)
sam build -t aws/template.yaml
sam deploy --stack-name sam-app --region us-east-1 \
  --parameter-overrides BucketName=<globally-unique-bucket-name> \
  --capabilities CAPABILITY_IAM --resolve-s3 --resolve-image-repos
```
The stack outputs `Bucket` and `WebEndpoint` (a Lambda Function URL). Full walkthrough: `docs/AWS_SETUP.md`.

## Test
**Web endpoint:** open `WebEndpoint` in a browser, choose a tile image, click *Inspect*.
Or from a terminal:
```bash
curl -X POST "<WebEndpoint>" -H "content-type: application/json" \
  -d "{\"image\":\"$(base64 -w0 samples/demo/test/tile_019.jpg)\",\"name\":\"tile_019.jpg\"}"
```
Expected for `tile_019.jpg`: grade **REJECT**, route **Recycle**, status `awaiting_approval`, defect `crack`.
Expected for `tile_001.jpg`: grade **B** (stain), route **Packer 2**.
Expected for `tile_011.jpg`: grade **A**, route **Packer 1**, status `auto_executed`.

**S3 trigger:**
```bash
aws s3 cp samples/demo/test/tile_001.jpg s3://<bucket>/incoming/tile_001.jpg
aws s3 cp s3://<bucket>/results/tile_001.json -      # appears after ~10 s
```
Logs: CloudWatch → `/aws/lambda/<function-name>`.

## Limitations
- All public results are on **synthetic** slate-effect tiles, which are easier than real line images
  (even lighting, one tile per frame, known defect sizes).
- The reference is learned from ~20 tiles of **one** design; a new design or glaze needs its own reference set.
- Very small edge chips can be missed (1 of 40 on the unseen set) — the most serious error, because a
  reject would go to a packer. A lower chip threshold trades this for more false rejects.
- Tiny spots are graded A on purpose; the size limit is a business setting, not a learned value.
- Real-camera validation has only been a small local sanity check (`eval/real_check.py`); no real
  factory images are published.
- Lambda cold start adds a few seconds to the first request after idle.

## Responsible use
- **A person decides every reject.** The agent only auto-routes A and B; nothing is sent to recycling
  without a supervisor clicking *Approve recycle*, and they can override to B.
- **Deterministic, explainable rules.** Grades come from measured defects with boxes drawn on the image;
  the optional Bedrock step only writes the shift note and never changes a decision.
- **No real factory or personal data in this repo or demo** — see `docs/DATA.md`. Private real images stay
  local and git-ignored; only summary numbers may be reported, with the owner's permission.
- **Low cost and contained:** uploads expire after 14 days (S3 lifecycle), a USD 10 budget alarm is set,
  and the stack is deleted after judging.
- It is a QC **assistant**, not a replacement for line inspectors or a safety system.

## Repo layout
| Folder | What |
|---|---|
| `pipeline/` | `tile_qc.py` (build / inspect / eval), `make_demo_tiles.py` (public synthetic data) |
| `agent/` | Grade → packer / recycle routing, human gate, optional Bedrock shift note |
| `aws/` | Lambda handler, container Dockerfile, SAM template (S3 → Lambda) |
| `ui/` | Streamlit approval dashboard for REJECT tiles (`ui/app.py`) |
| `eval/` | Metrics, validation plan, local-only real-image check (`real_check.py`) |
| `docs/` | AWS setup, team plan, data policy |

## Data
All images in this repo are **synthetic**. See `docs/DATA.md`.
