# Evaluation (owner: Nandani)
1. `python pipeline/tile_qc.py eval --ref models/reference.json --test samples/demo/test` → precision / recall,
   per-defect results, overlays in `outputs/`.
2. Repeat on an unseen seed (`make_demo_tiles.py --seed 99 --out /tmp/s2`) to check it generalises.
3. Optional: MVTec AD tile benchmark (licence permitting).
4. Report: precision, recall, grade confusion (A/B/REJECT), and seconds per tile on Lambda.
