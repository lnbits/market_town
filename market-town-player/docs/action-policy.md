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
- Restock enough units for likely demand. If stock is zero, submit a small positive recovery restock unless you deliberately intend to stop operating; negative cash does not make a valid restock unaffordable to the game.
- Keep maintenance and quality at zero during recovery; restore discretionary spending only after cash recovers.
- Avoid pricing far above unit cost: price directly reduces demand, including when you are the only business in the district.
- Do not over-restock when demand is uncertain.
- Include a short `reasoning` field with every submission.
- Do not raise price, maintenance, and quality every epoch; change one knob only when the data justifies it, then assess sell-through and `cash_after - cash_before` in the next snapshot.

Use the district and business type fields from the public world state:

- Higher `footfall_base` can justify restocking closer to capacity.
- Higher `price_sensitivity` argues for a price a little below 2x unit cost.
- Higher `affluence` can tolerate a higher price.
- Higher `quality_preference` argues for a larger quality budget if cash allows.
- `base_capacity_units` is a practical upper bound for early restock until demand history exists.

After one or more epochs, adapt from `recent_snapshots` and the leaderboard:

- If sold units are close to stock or capacity, increase restock next epoch.
- If units sold are low, reduce price and avoid over-restocking.
- If stock is zero, use a small positive recovery restock with zero maintenance/quality unless you deliberately intend to stop operating; negative cash alone is not a reason to submit zero restock.
- If cash is falling, reduce discretionary maintenance/quality spend before cutting recovery restock.
- Treat `profit_sat` as net of restock and use `cash_after - cash_before` to verify whether an epoch made money.
- If reputation/quality appears to lag competitors and margins are positive, increase quality gradually.

## Before Submitting

Fetch the agent session and verify:

- `current_epoch` exists.
- `current_epoch.epoch_number` is the epoch being submitted.
- `business.id` matches the submitted `business_id`.
- `latest_submission` is absent, invalid, or for a different epoch. If there is already a valid submission for the current epoch, replace it only before cutoff and only to correct a concrete mistake such as zero stock with zero restock.
- The submission is before cutoff.
- All numeric fields are non-negative, except `price_sat`, which must be at least 1.

## Retry Rules

If a submission fails:

1. Fetch session again.
2. Check whether the epoch changed.
3. Correct validation errors.
4. Resubmit only if still before cutoff.

Latest valid submission for the same epoch wins.
