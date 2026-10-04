# Team Cloud Catalyst — plan

**Idea:** Tile QC Inspector — learn "good" from ~20 best tiles, inspect each tile for cracks, chips,
spots and stains, grade A / B / REJECT, and let an agent route tiles to Packer 1, Packer 2 or
Recycle. Rejects wait for **human approval**.

| Owner | Scope |
|---|---|
| **Edmund** | Vision pipeline (`pipeline/`), agent logic (`agent/`), AWS deployment (`aws/`), repo & infra |
| **Nandani** | Approval UI (`ui/`), evaluation (`eval/`), technical report, demo video, Devpost form |

| Dates | Milestone |
|---|---|
| by Oct 7 | Idea switched to tiles · pipeline + synthetic data working ✅ · AWS account + budget alarm |
| Oct 6–12 | Lambda + S3 deployed · optional MVTec tile benchmark · private real-image check (local only) |
| Oct 13–19 | Approval UI connected to `results/` · evaluation numbers · Bedrock shift note |
| Oct 20–25 | Demo video · report · Devpost submitted (**by Oct 25**) |

**Rules:** feature branches + pull requests into `main` · one stand-up message a day · no secrets
and **no real factory images** in git (see `docs/DATA.md`).
