## Inspiration

Every hackathon we've built together has landed on the same shape: something gets detected, an agent decides what it means, a human approves before anything happens, and the outcome gets logged. We built that loop for support tickets (IncidentFlow) and script coverage (Greenlight Desk), but it never touched the physical world.

One of us used to commission camera inspection machines on ceramic tile lines. At the end of the kiln, people still decide, tile by tile, what is first quality, what is second quality and what goes back to be crushed and recycled. That decision is exactly what OpenCV's Agentic Vision award asks for: a vision result that changes what the system does next, not just a label on a picture.

## What it does

SentryLoop is a tile quality-control inspector.

- **Learn "good":** run about 20 of the best tiles past the camera. SentryLoop learns the normal range of surface relief, brightness and edges.
- **Inspect:** every new tile is located, straightened and checked for cracks, chips, spots and stains.
- **Grade:** each tile gets A, B or REJECT based on defect type and size.
- **Act:** an agent routes the tile: A → Packer 1, B → Packer 2, REJECT → Recycle.
- **Human gate:** nothing is recycled until a supervisor approves (or overrides to B). Every decision is logged.

## How we built it

- **OpenCV 5** for the vision pipeline: Otsu + contour + perspective warp to find and straighten the tile; Gaussian high-pass to remove lighting gradients; dark/bright deviation maps and connected components for cracks, pits and spots; an edge-hole check for chips; patch statistics for stains and shade.
- **Statistics, not pixel matching.** Slate- and stone-effect tiles have a different random texture on every piece, so comparing to a "golden image" fails. Thresholds are learned from the reference tiles (extreme percentiles of their own surface), so anything outside "normal" stands out.
- **Agent layer in Python:** deterministic, explainable grade → route rules, plus a human approval queue for rejects. An optional Amazon Bedrock step can write a plain-English shift note; it never makes the decision.
- **AWS:** a tile image lands in S3 `incoming/` and triggers a container-image Lambda (built with AWS SAM) that inspects, decides and writes the result to `results/`. The same Lambda serves a public web page through a Function URL for one-click testing.
- **Approval UI (Streamlit):** reads results from S3, draws the defect boxes, and lets a supervisor approve recycling or override to B. Decisions are saved back to S3.

## Challenges we ran into

- **Random textures.** Our first detector flagged the slate texture itself as defects. Switching to learned statistics and a light Gaussian smoothing removed the false alarms.
- **Cracks vs spots vs chips.** A crack near the edge looked like a chip, and broken crack segments looked like spots. Shape rules (length, and how much of its box a blob fills) plus a dedicated edge-hole check fixed that.
- **Shipping OpenCV to Lambda.** OpenCV is too large for a Lambda zip package, so we packaged it as a container image and pinned versions for Python 3.12.
- **Data we could share.** Real line images belong to factories, so the public demo uses synthetic slate-effect tiles we generate ourselves. Real images were only used privately to sanity-check the method.

## Accomplishments that we're proud of

- **Defect detection:** precision 1.00 / recall 1.00 on the demo set and 1.00 / 0.95 on an unseen set (one small edge chip missed), with **zero false alarms on good tiles**.
- **Exact grade agreement:** 39/40 (demo) and 37/40 (unseen); the misses are tiny spots graded A instead of B by design, plus the one missed chip.
- About **60 ms per tile** on a CPU.
- A full loop from camera to packer decision to human approval, live on AWS, not just a detector.

## What we learned

Grading is a business decision, not just a vision output. Making the rules explainable, and putting a person in front of every reject, is what makes a factory trust the system.

## What's next

- Validate on real line cameras and multi-light (grazing-light) captures.
- Add colour-shade grading per batch.
- A live dashboard per shift, with defect trends that point maintenance to the press or kiln causing them.
