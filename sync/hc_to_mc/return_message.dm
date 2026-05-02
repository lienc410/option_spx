Hi MC — attaching HC return package for the 2026-05-01 sync round:

- sync/hc_to_mc/HC_return_2026-05-02.md

Top-line:
- HC reproduced `SPEC-074 / 077 / 078 / 079 / 080`
- tieout #2 and #3 both PASS
- `Q021` is now closed on HC side
- `Q038` has already been flipped to `shadow` on old Air live runtime
- `Q039` remains research-only on HC side

Two items where HC is asking for MC-side tie-out inputs:
1. `SPEC-077 AC3` magnitude gap
   - HC no longer believes this is a dashboard bug or SPEC-080 issue
   - we need MC’s minimal full-sample tie-out fields (ROE formula, denominator, trade-count / exit-reason split, etc.)
2. `Q039` residual IC regular gap
   - HC would like the MC 6-trade IC regular ledger before widening attribution work

Also included:
- HC has now aligned directionally with MC on `Q036` (escalate / productization-stack direction)
- `SPEC-075 / 076` were not implemented in this sprint, but HC is requesting the next-batch adoption input package so we can line up the next adoption pass cleanly

Please treat this package as incremental on top of prior confirmed HC↔MC sync context, not a reset of earlier aligned items.
