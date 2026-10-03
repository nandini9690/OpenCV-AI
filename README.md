# Cloud Catalyst · Site Safety Monitor
**OpenCV AI Competition 2026 (powered by AWS) — Agentic Vision track**
Team: Edmund Anthony · Nandani Chauhan

Construction and industrial sites rely on people watching camera feeds. This project lets the camera
watch for the two most common risks — **people entering restricted machinery zones** and **missing PPE** —
and lets an AI agent propose the response, with a **human approval gate** for anything high-severity.

## How it works
```
camera clip ──► S3 incoming/ ──► Lambda (OpenCV pipeline) ──► events
                                         │
                                         ▼
                              agent: severity → action ──► auto-execute (low/medium)
                                         │
                                         └──► awaiting human approval (high) ──► UI
```

## Repo layout
| Folder | What |
|---|---|
| `pipeline/` | OpenCV detection: background subtraction + zone polygons; optional ONNX PPE model |
| `agent/` | Rule-based decisions, human gate, optional Bedrock incident summaries |
| `aws/` | Lambda handler, container Dockerfile, SAM template (S3 → Lambda) |
| `ui/` | Approval dashboard |
| `eval/` | Ground-truth clips and metrics |
| `docs/` | AWS setup checklist, team plan |

## Quick start
```bash
pip install -r requirements.txt
python pipeline/detect.py --video samples/site.mp4 --preview     # Esc to quit
python agent/decide.py                                         # writes outputs/decisions.json
```
Edit `pipeline/zones.json` to draw restricted zones (coordinates are 0–1 fractions of the frame).

See `docs/AWS_SETUP.md` to deploy and `docs/TEAM_PLAN.md` for owners and dates.
