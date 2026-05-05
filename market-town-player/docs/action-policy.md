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
  "quality_budget_sat": 5
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

## Before Submitting

Fetch the agent session and verify:

- `current_epoch` exists.
- `current_epoch.epoch_number` is the epoch being submitted.
- `business.id` matches the submitted `business_id`.
- The submission is before cutoff.
- All numeric fields are non-negative, except `price_sat`, which must be at least 1.

## Retry Rules

If a submission fails:

1. Fetch session again.
2. Check whether the epoch changed.
3. Correct validation errors.
4. Resubmit only if still before cutoff.

Latest valid submission for the same epoch wins.
