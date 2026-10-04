# Approval UI (owner: Nandani)
Reads `results/*.json` from S3 (or `outputs/decisions.json` locally) and shows:
- a live counter: A / B / REJECT for the shift, plus the shift note
- each REJECT tile: overlay image (`outputs/overlay_*.jpg`), defect types, **Approve recycle / Override to B** buttons
Suggested stack: one Streamlit app (`ui/app.py`).
