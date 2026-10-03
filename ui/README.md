# Approval UI (owner: Nandani)
Reads `results/*.json` (or `outputs/decisions.json` locally) and shows each decision:
severity, summary, snapshot, and **Approve / Reject** buttons for items with `status: awaiting_approval`.
Suggested stack: a single Streamlit app (`ui/app.py`) or a static page + API Gateway later.
