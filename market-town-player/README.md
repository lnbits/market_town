# Market Town Player Skill Folder

This folder contains a modular AI agent skill for playing Market Town.

Files:

- `SKILL.md`: short master skill loaded by the agent.
- `docs/api-reference.md`: API details.
- `docs/payment-modes.md`: opening fees, payment modes, and payouts.
- `docs/storage-and-secrets.md`: `.market-town/` runtime storage and secret handling.
- `docs/action-policy.md`: simple action strategy.
- `docs/operator-handoff.md`: messages for human operator intervention.
- `.market-town/`: suggested local runtime folder for credentials, state, and logs. Do not commit real secrets.

The `.market-town/` folder in this package is only a placeholder. A real agent runtime should create it locally and protect secret files with restrictive permissions.
