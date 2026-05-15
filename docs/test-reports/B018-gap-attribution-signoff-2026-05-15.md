# B018-gap-attribution-signoff-2026-05-15

## Summary
- Batch: `B018-gap-root-cause-attribution`
- Result: `PASS`
- Scope: real-data attribution + three-axis parameter sweep on B014 snapshot
- Snapshot: `regime-adaptive:b69883b08eedea7d`

## Verification
- Attribution / sweep unit tests: `47 passed`
- Full test suite: `573 passed`
- `ruff check trade tests scripts`: passed
- `mypy trade`: passed
- `compileall -q trade tests scripts`: passed

## High-level findings
- `l2_vol_scaling` is the dominant drag on both B010 and B013.
- `l1_gating` is a secondary drag for B013, but not the root cause.
- `vol_target` and `cadence` are the actionable axes; `universe` ablation is mostly constrained by defensive-asset invariants and does not produce a clean dominance story.
- The report keeps B018 research-only and does not mutate any default strategy parameter.

## Backlog
- Added `BL-B018-S1` to `backlog.json` for a follow-up B010 cadence / vol-target retune candidate.

## State machine
- `progress.json.status` set to `done`.
- `progress.json.docs.signoff` points to this signoff file.

## Conclusion
B018 is signable. The real-data attribution and sweep evidence are sufficient to close the batch, and the remaining work is a follow-up research batch rather than a B018 defect.

_Disclaimer: research-only; never authorizes paper or live trading._
