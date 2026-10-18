# Approval UI
`ui/app.py` is a Streamlit app. Run it with `streamlit run ui/app.py` (local `outputs/`) or
`streamlit run ui/app.py -- --bucket <bucket>` (live `results/*.json` from S3).

It shows the A / B / REJECT counts for the shift and a queue of REJECT tiles with the defect
boxes drawn on the image. **Approve recycle** or **Override to B** is written to
`approvals/<tile>.json` in S3, or `outputs/approvals.json` locally.
