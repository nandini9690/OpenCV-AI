# Cloud Catalyst · Tile QC Inspector
**OpenCV AI Competition 2026 (powered by AWS) — Agentic Vision track**
Team: Edmund Anthony · Nandani Chauhan

Ceramic tile factories still rely on people at the end of the kiln line to spot cracks, chips,
spots and stains — and to decide which tiles are first quality, second quality or scrap.
This project teaches a camera what a **good** tile looks like from about **20 of the best tiles**,
then inspects every new tile, **grades it** and lets an AI agent **route it** to the right packer —
with a **human approval gate** before anything is sent to recycling.

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

## Results (public synthetic set)
| Set | Tiles | Precision | Recall |
|---|---|---|---|
| Demo set (seed 7) | 40 | 1.00 | 1.00 |
| Unseen set (seed 99) | 40 | 1.00 | 0.95 (1 small chip missed) |

Synthetic tiles are easier than real ones — real-camera validation is part of the evaluation plan (`eval/`).

## Quick start
```bash
pip install -r requirements.txt
python pipeline/make_demo_tiles.py                                   # 20 reference + 40 test tiles
python pipeline/tile_qc.py build   --refs samples/demo/reference     # learn "good"
python pipeline/tile_qc.py eval    --ref models/reference.json --test samples/demo/test
python agent/decide.py                                               # routes + shift note
```
Overlays with boxes and grades are written to `outputs/`.

## Repo layout
| Folder | What |
|---|---|
| `pipeline/` | `tile_qc.py` (build / inspect / eval), `make_demo_tiles.py` (public synthetic data) |
| `agent/` | Grade → packer / recycle routing, human gate, optional Bedrock shift note |
| `aws/` | Lambda handler, container Dockerfile, SAM template (S3 → Lambda) |
| `ui/` | Approval dashboard for REJECT tiles |
| `eval/` | Metrics and validation plan |
| `docs/` | AWS setup, team plan, data policy |

## Data
All images in this repo are **synthetic**. See `docs/DATA.md`.
