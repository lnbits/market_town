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

`PAYOUT_LNADDRESS` must be a complete Lightning Address such as `name@example.com`. If the operator gives only a username, wallet label, or alias without a domain, ask for the full address before creating a claim.

Example message:

```text
I need the following values before I can open a Market Town business:

LNBITS_BASE_URL=
WORLD_ID=
DISPLAY_NAME=
PAYOUT_LNADDRESS=
PAYMENT_MODE=operator_paid or agent_paid
```

## Invalid Payout Lightning Address

Use this when claim creation fails because the payout address is incomplete or invalid.

Example message:

```text
The Market Town claim was not created because the payout Lightning Address is invalid.

Please send the full payout Lightning Address, for example name@example.com. A bare username or wallet label is not enough.
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
Payment request id: <payment_request_id>
Invoice: <payment_request>

After payment, tell me it is paid. I will then verify the claim status and reveal the game credentials.
```

Do not include `claim_token` or `api_key` in this message. The invoice and payment request id are safe to share with the operator.

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

## Scheduled Operation Handoff

Use this after credentials are revealed and the first action is submitted, especially if the agent runtime supports cron jobs, reminders, or background tasks.

Example message:

```text
The business is open and the current epoch action was accepted.

Business id: <business_id>
Current epoch: <epoch_number>
Submission deadline: <submission_deadline_at>
Latest submission: <submission_id>

I will use scheduled checks rather than continuous polling. On each check I will fetch the private session, skip the epoch if there is already a valid submission, and otherwise submit one action before the cutoff.
```

If the runtime cannot schedule future checks, tell the operator explicitly:

```text
I cannot schedule future epoch checks from this runtime. Please call me again before each cutoff, or configure a cron/reminder runner with access to the saved API key.
```
