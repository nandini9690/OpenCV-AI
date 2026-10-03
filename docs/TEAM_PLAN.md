# Team Cloud Catalyst — plan

**Idea:** Site Safety Monitor — OpenCV detects restricted-zone intrusion and missing PPE on site cameras;
an agent proposes actions, and high-severity actions wait for **human approval** before execution.

| Owner | Scope |
|---|---|
| **Edmund** | OpenCV pipeline (`pipeline/`), agent logic (`agent/`), AWS deployment (`aws/`), repo & infra |
| **Nandani** | Approval UI (`ui/`), evaluation (`eval/`), technical report, demo video, Devpost form |

| Dates | Milestone |
|---|---|
| by Oct 5 | Idea locked · repo scaffold · AWS account + budget alarm · sample clips collected |
| Oct 6–12 | Pipeline grading sample clips locally · Lambda + S3 deployed |
| Oct 13–19 | Agent loop + approval UI connected · evaluation numbers |
| Oct 20–25 | Demo video · report · Devpost submitted (**by Oct 25**) |

**Rules:** feature branches + pull requests into `main` · one stand-up message a day in Slack DM · no secrets in git.
