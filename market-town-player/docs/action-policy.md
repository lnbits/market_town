# Action Policy

The agent must submit one valid action per active epoch before cutoff.

Action schema:

```json
{
  "epoch": 1,
  "business_id": "business-id",
  "price_sat": 220,
  "restock_units": 40,
  "maintenance_budget_sat": 6,
  "quality_budget_sat": 5,
  "reasoning": "Initial conservative policy with price near 2x unit cost."
}
```

## Basic Strategy

Until the agent has enough history:

- Keep `price_sat` near 2x the business type unit cost.
- Restock enough units for likely demand.
- Avoid spending all available cash.
- Spend small positive amounts on maintenance and quality.
- Increase quality gradually if margins allow.
- Do not over-restock when demand is uncertain.
- Include a short `reasoning` field with every submission.
- Do not raise price, maintenance, and quality every epoch; adjust a knob only when the data justifies it.

Use the district and business type fields from the public world state:

- Higher `footfall_base` can justify restocking closer to capacity.
- Higher `price_sensitivity` argues for a price a little below 2x unit cost.
- Higher `affluence` can tolerate a higher price.
- Higher `quality_preference` argues for a larger quality budget if cash allows.
- `base_capacity_units` is a practical upper bound for early restock until demand history exists.

After one or more epochs, adapt from `recent_snapshots` and the leaderboard:

- If sold units are close to stock or capacity, increase restock next epoch.
- If units sold are low, reduce price and avoid over-restocking.
- If cash is falling, reduce discretionary maintenance/quality spend before cutting restock too far.
- If reputation/quality appears to lag competitors and margins are positive, increase quality gradually.

## Before Submitting

Fetch the agent session and verify:

- `current_epoch` exists.
- `current_epoch.epoch_number` is the epoch being submitted.
- `business.id` matches the submitted `business_id`.
- `latest_submission` is absent, invalid, or for a different epoch. If there is already a valid submission for the current epoch, do not submit again unless intentionally replacing it.
- The submission is before cutoff.
- All numeric fields are non-negative, except `price_sat`, which must be at least 1.

## Retry Rules

If a submission fails:

1. Fetch session again.
2. Check whether the epoch changed.
3. Correct validation errors.
4. Resubmit only if still before cutoff.

Latest valid submission for the same epoch wins.
