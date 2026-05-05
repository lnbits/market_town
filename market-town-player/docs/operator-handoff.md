# Operator Handoff

Use this file when the agent needs human help.

## Missing Required Inputs

If required inputs are missing, ask the operator for only the missing values.

Required inputs:

```text
LNBITS_BASE_URL
WORLD_ID
DISPLAY_NAME
PAYOUT_LNADDRESS
PAYMENT_MODE
```

Example message:

```text
I need the following values before I can open a Market Town business:

LNBITS_BASE_URL=
WORLD_ID=
DISPLAY_NAME=
PAYOUT_LNADDRESS=
PAYMENT_MODE=operator_paid or agent_paid
```

## Operator Payment Request

Use this when `PAYMENT_MODE=operator_paid`, or when the agent has no wallet tool.

Example message:

```text
I created a Market Town business claim and need the opening invoice paid before I can continue.

World: <world_id>
Display name: <display_name>
District: <district_id>
Business type: <business_type_id>
Amount: <amount_sat> sats
Invoice: <payment_request>

After payment, I will check the claim status and reveal the game credentials.
```

Do not include `claim_token` in this message.

## Spending Limit Approval

Use this when the opening fee exceeds `MAX_OPENING_FEE_SAT`.

Example message:

```text
The opening fee is <amount_sat> sats, which exceeds the configured limit of <max_opening_fee_sat> sats. Please approve a higher limit or choose a cheaper business type.
```

## Payment Settled But Unclaimed

Use this when claim status is `paid_unclaimed`.

Example message:

```text
The invoice was paid, but the claim is marked paid_unclaimed. This usually means the district was full at settlement time. I will not call reveal. Please choose whether to open a new claim or contact the Market Town operator.
```

## Lost Credentials

If `claim_token` or `api_key` is lost:

```text
I cannot safely continue because a required credential is missing. The claim token and API key are only shown once. Please provide recovery instructions or create a new claim.
```
