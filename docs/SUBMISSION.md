# Submission kit: Tile QC Inspector (OpenCV AI Competition 2026)

Deadline: **Sun 26 Oct, 11:59 pm PT (Mon 27 Oct, 2:59 pm SGT)**. Team target: **Sat 25 Oct**.
Track: **Agentic Vision only**. Do not tick other prize categories.

## Status (25 Oct)
| Item | Owner | Status |
|---|---|---|
| Pipeline + agent + eval numbers | Edmund | ✅ in repo |
| Lambda on OpenCV 5.0.0 + web endpoint | Nandani | ✅ live (tiles 011 / 019 / 037 checked) |
| README with live URL | Edmund | ✅ this commit |
| S3 trigger on `incoming/` runs the new function | Nandani | ✅ works on the live bucket `cloud-catalyst-tileqc-nc2026bc` (re-test after the 25 Oct redeploy) (tile_019 → REJECT crack, awaiting_approval) |
| Deployed template / handler changes pushed to GitHub | Nandani | ⬜ repo still shows the 15 Oct version |
| Approval UI against the live bucket | Nandani | ⬜ |
| Budget alarm | Nandani | ⬜ confirm |
| Report | Nandani (draft below) | ⬜ |
| Video ≤ 5 min, YouTube **public** | Nandani (script below) | ⬜ |
| Zip of code, Devpost form | Nandani | ⬜ |

### Live bucket (updated 26 Oct)
The 25 Oct redeploy of stack `cloud-catalyst-tileqc-v2` moved it to a new bucket. **Use `cloud-catalyst-tileqc-nc2026bc` everywhere** (UI, Devpost, video). The previous bucket `cloud-catalyst-tileqc-nc2026-v2` was not empty, so CloudFormation kept it (DELETE_FAILED is harmless); it no longer has a trigger. Web uploads now also go to `nc2026bc` (`BUCKET_NAME` in the template), so web results show in the approval UI too:
```bash
aws s3 cp samples/demo/test/tile_019.jpg s3://cloud-catalyst-tileqc-nc2026bc/incoming/tile_019.jpg
# wait ~10 s
aws s3 cp s3://cloud-catalyst-tileqc-nc2026bc/results/tile_019.json -
streamlit run ui/app.py -- --bucket cloud-catalyst-tileqc-nc2026bc
```
Older buckets (`cloud-catalyst-tileqc-nc2026`, `cloud-catalyst-tileqc-nc2026-v2`) no longer process uploads. Do not delete any stack or bucket until judging ends.

---

## Devpost text (draft)
**Tagline:** Learns "good" from 20 tiles, grades every tile, and routes it, with a person approving every reject.

**Inspiration:** At the end of a ceramic kiln line, people still check each tile by eye for cracks,
chips, spots and stains, then decide first quality, second quality or scrap. It is tiring, subjective
work, and stone-effect tiles make it harder because no two tiles look the same.

**What it does:** Upload a tile photo (web page or S3). OpenCV 5 finds and straightens the tile,
compares its surface against statistics learned from about 20 good tiles, and lists defects. An agent
grades it **A / B / REJECT** and routes it: A → Packer 1, B → Packer 2 automatically. Every REJECT
waits in an approval UI until a person clicks *Approve recycle* or *Override to B*.

**How we built it:** OpenCV 5.0 (perspective correction, high-pass relief maps, morphology, blob and
edge analysis) · Python 3.12 · AWS Lambda (container image) + S3 trigger + Function URL · AWS SAM ·
Streamlit approval UI reading `results/` from S3.

**Challenges:** Random stone textures (solved by learning normal ranges, not pixel matching); OpenCV
is too big for a Lambda zip (container image); a slow 1.4 GB image push; IAM permissions for web uploads.

**Accomplishments:** Precision 1.00 / recall 0.95 on an unseen synthetic set; ~60 ms per tile; the
agent can never send a tile to recycling without a person.

**What we learned:** Statistics beat templates for natural textures; human-in-the-loop design is
simple to build when the agent's actions are limited on purpose.

**What's next:** Validate on real line images (with permission), add a reference set per tile design,
an end-of-shift summary, and an approval step in a factory messaging app.

## Testing instructions (paste into Devpost)
1. Open https://hkdbd4v3q4mfndvdjo4kvxzndm0ddjlj.lambda-url.us-east-1.on.aws/
2. Get test tiles: clone the repo, `pip install -r requirements.txt`, `python pipeline/make_demo_tiles.py`
   (creates `samples/demo/test/`).
3. Upload `tile_011.jpg` → **A, Packer 1, auto_executed**. Upload `tile_019.jpg` → **REJECT, crack,
   awaiting_approval**. Upload `tile_037.jpg` → **REJECT, chip + spot**. The response shows `"opencv": "5.0.0"`.
4. Offline: follow *Quick start* in the README to reproduce the precision/recall numbers.
The first request after idle can take a few seconds (Lambda cold start).

---

## Video script (target 3:30, max 5:00)
| Time | Show | Say |
|---|---|---|
| 0:00–0:25 | Title slide + a photo of tiles (synthetic or stock) | The problem: manual end-of-line tile checks; stone textures make it hard. |
| 0:25–0:55 | README diagram | Learn "good" from 20 tiles → inspect → grade → agent routes → human approves rejects. |
| 0:55–1:40 | Live web page: tile_011 (A), tile_019 (REJECT crack), tile_037 (REJECT chip+spot) | Point at grade, route, status, `"opencv": "5.0.0"`. |
| 1:40–2:20 | Overlay image (`docs/sample_overlays.jpg`) | How each defect is found (crack, chip, spot, stain). |
| 2:20–3:00 | Streamlit approval UI: waiting rejects → click *Approve recycle* | Nothing goes to recycling without a person. |
| 3:00–3:20 | Results table (precision/recall, ~60 ms/tile) | Honest numbers, including the one missed chip. |
| 3:20–3:30 | Architecture: S3 → Lambda (container) → results → UI | Built on AWS with OpenCV 5. Thank you. |

Record with Clipchamp's own screen recorder or Xbox Game Bar (Win+G). In Snipping Tool, pressing **X**
discards the recording.

## Report outline (draft)
1. Problem and users (end-of-line tile inspection)
2. Approach: reference statistics instead of templates; the OpenCV 5 pipeline step by step
3. Agent and human approval gate (A/B auto, REJECT needs approval)
4. AWS architecture (S3, Lambda container, Function URL, SAM, approval UI)
5. Evaluation: demo and unseen sets, precision/recall, grade agreement, speed
6. Limitations (synthetic data, one tile design, small chips) and responsible use
7. Next steps
