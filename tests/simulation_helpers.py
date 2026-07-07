from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from lnbits.core.models import Payment
from lnbits.core.models.payments import PaymentState
from market_town.crud import (
    create_epoch,
    get_world_by_id,
    list_business_types,
    list_districts,
    update_world,
)
from market_town.models import (
    ActionPayload,
    AgentCredentialReveal,
    ClaimBusinessRequest,
    CreateWorld,
    Epoch,
    World,
)
from market_town.services import (
    create_business_claim,
    ensure_world_bootstrap,
    epoch_window,
    get_agent_session,
    payment_received_for_claim,
    reveal_claim_credentials,
    season_number_for_epoch,
    submit_action,
    utc_now,
    world_started_at_for_epoch,
)


@dataclass
class SimAgent:
    credentials: AgentCredentialReveal
    api_key: str
    agent_id: str
    business_id: str
    display_name: str


def patch_lightning(monkeypatch):
    calls = SimpleNamespace(created_invoices=[], paid_invoices=[], tributes=[])
    invoice_counter = {"value": 0}

    async def fake_create_invoice(*args, **kwargs):
        calls.created_invoices.append(kwargs)
        invoice_counter["value"] += 1
        return SimpleNamespace(
            payment_hash=f"hash-{uuid4().hex}-{invoice_counter['value']}",
            bolt11=f"lnbc1sim{invoice_counter['value']}",
        )

    async def fake_pay_invoice(**kwargs):
        calls.paid_invoices.append(kwargs)
        payment_hash = f"paid-{uuid4().hex}"
        return Payment(
            checking_id=payment_hash,
            payment_hash=payment_hash,
            wallet_id=kwargs["wallet_id"],
            amount=-(kwargs["max_sat"] or 0) * 1000,
            fee=0,
            bolt11=kwargs["payment_request"],
            status=PaymentState.SUCCESS.value,
        )

    async def fake_pay_tribute(tribute: int, wallet_id: str):
        calls.tributes.append({"tribute": tribute, "wallet_id": wallet_id})
        return None

    async def fake_get_pr_from_lnurl(lnaddress: str, amount_msat: int, comment: str):
        return f"lnbc1payout-{lnaddress}-{amount_msat}-{comment}"

    monkeypatch.setattr("market_town.services.create_invoice", fake_create_invoice)
    monkeypatch.setattr("market_town.services.pay_invoice", fake_pay_invoice)
    monkeypatch.setattr("market_town.services.pay_tribute", fake_pay_tribute)
    monkeypatch.setattr("market_town.services.get_pr_from_lnurl", fake_get_pr_from_lnurl)
    return calls


async def bootstrap_world(
    *,
    name: str = "Simulation Market",
    wallet_id: str = "sim-wallet",
    fee_wallet_id: str | None = "sim-fees",
    operator_fee_percent: float = 10,
    season_length_epochs: int = 2,
) -> World:
    return await ensure_world_bootstrap(
        uuid4().hex,
        CreateWorld(
            name=name,
            wallet_id=wallet_id,
            fee_wallet_id=fee_wallet_id,
            operator_fee_percent=operator_fee_percent,
            season_length_epochs=season_length_epochs,
        ),
    )


async def default_claim_options(world_id: str):
    districts = await list_districts(world_id)
    business_types = await list_business_types(world_id)
    return districts[0], business_types[0]


async def create_paid_agent(
    world: World,
    *,
    display_name: str,
    district_id: str,
    business_type_id: str,
    payout_lnaddress: str | None = None,
) -> SimAgent:
    claim = await create_business_claim(
        ClaimBusinessRequest(
            world_id=world.id,
            display_name=display_name,
            district_id=district_id,
            business_type_id=business_type_id,
            payout_lnaddress=payout_lnaddress or f"{display_name}@example.com",
        )
    )
    paid = await payment_received_for_claim(
        SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
    )
    if not paid:
        raise AssertionError("claim did not settle")
    credentials = await reveal_claim_credentials(claim.claim_token)
    return SimAgent(
        credentials=credentials,
        api_key=credentials.api_key,
        agent_id=credentials.agent_id,
        business_id=credentials.business_id,
        display_name=display_name,
    )


async def submit_strategy(
    world_id: str,
    agent: Any,
    *,
    epoch_number: int,
    price_sat: int = 220,
    restock_units: int = 40,
    maintenance_budget_sat: int = 6,
    quality_budget_sat: int = 5,
    reasoning: str | None = None,
):
    return await submit_action(
        world_id,
        agent.api_key,
        ActionPayload(
            epoch=epoch_number,
            business_id=agent.business_id,
            price_sat=price_sat,
            restock_units=restock_units,
            maintenance_budget_sat=maintenance_budget_sat,
            quality_budget_sat=quality_budget_sat,
            reasoning=reasoning,
        ),
    )


async def ensure_epoch(world: World, epoch_number: int) -> Epoch:
    started_at, submission_deadline_at, digest_at = epoch_window(world, epoch_number)
    return await create_epoch(
        Epoch(
            id=uuid4().hex,
            world_id=world.id,
            epoch_number=epoch_number,
            season_number=season_number_for_epoch(world, epoch_number),
            started_at=started_at,
            submission_deadline_at=submission_deadline_at,
            digest_at=digest_at,
            status="open",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )


async def advance_world_to_epoch(world: World, epoch_number: int) -> World:
    refreshed = await get_world_by_id(world.id)
    if not refreshed:
        raise AssertionError("world disappeared")
    return await update_world(
        refreshed.copy(
            update={
                "started_at": world_started_at_for_epoch(refreshed, epoch_number, utc_now()),
                "current_epoch_number": epoch_number,
                "current_season_number": season_number_for_epoch(refreshed, epoch_number),
            }
        )
    )


async def current_session(world_id: str, agent: SimAgent):
    return await get_agent_session(world_id, agent.api_key)
