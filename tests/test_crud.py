import asyncio
from types import SimpleNamespace
from uuid import uuid4

from market_town.crud import (  # type: ignore[import]
    get_payment_request,
    get_world_for_user,
    list_business_types,
    list_districts,
    list_snapshots_for_business,
)
from market_town.models import (  # type: ignore[import]
    ActionPayload,
    ClaimBusinessRequest,
    CreateWorld,
)
from market_town.services import (  # type: ignore[import]
    build_public_world_state,
    create_business_claim,
    ensure_current_epoch,
    ensure_world_bootstrap,
    get_agent_session,
    get_claim_status,
    payment_received_for_claim,
    resolve_epoch,
    reveal_claim_credentials,
    seed_defaults,
    submit_action,
)


def test_bootstrap_world_seeds_defaults_once():
    async def _run():
        user_id = uuid4().hex
        world = await ensure_world_bootstrap(
            user_id,
            CreateWorld(
                name="Market Alpha",
                wallet_id="wallet-1",
            ),
        )
        assert world.user_id == user_id

        districts = await list_districts(world.id)
        business_types = await list_business_types(world.id)
        assert len(districts) == 6
        assert len(business_types) == 4

        await seed_defaults(world.id)
        assert len(await list_districts(world.id)) == 6
        assert len(await list_business_types(world.id)) == 4
        stored_world = await get_world_for_user(user_id)
        assert stored_world is not None
        assert stored_world.fee_wallet_id is None
        assert stored_world.current_epoch_number == 0
        assert await ensure_current_epoch(stored_world) is None

    asyncio.run(_run())


def test_paid_claim_reveals_credentials(monkeypatch):
    created_invoices = []
    paid_requests = []

    async def fake_create_invoice(*args, **kwargs):
        created_invoices.append(kwargs)
        if kwargs["wallet_id"] == "wallet-fees":
            return SimpleNamespace(payment_hash="hash-fee-1", bolt11="lnbc1operatorfee")
        return SimpleNamespace(payment_hash="hash-claim-1", bolt11="lnbc1markettown")

    async def fake_pay_tribute(*args, **kwargs):
        return None

    async def fake_pay_invoice(**kwargs):
        paid_requests.append(kwargs)
        return SimpleNamespace(ok=True)

    async def _run():
        monkeypatch.setattr("market_town.services.create_invoice", fake_create_invoice)
        monkeypatch.setattr("market_town.services.pay_tribute", fake_pay_tribute)
        monkeypatch.setattr("market_town.services.pay_invoice", fake_pay_invoice)

        world = await ensure_world_bootstrap(
            uuid4().hex,
            CreateWorld(name="Market Beta", wallet_id="wallet-2", fee_wallet_id="wallet-fees"),
        )
        districts = await list_districts(world.id)
        business_types = await list_business_types(world.id)

        claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="bot-merchant",
                district_id=districts[0].id,
                business_type_id=business_types[0].id,
                payout_lnaddress="bot@example.com",
            )
        )
        status = await get_claim_status(claim.payment_request_id)
        assert status.status == "pending"

        settled = await payment_received_for_claim(
            SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
        )
        assert settled is True

        payment_request = await get_payment_request(claim.payment_request_id)
        assert payment_request is not None
        assert payment_request.status == "paid"
        assert payment_request.operations_amount_sat > 0
        assert any(item["wallet_id"] == "wallet-fees" for item in created_invoices)
        assert any(item["wallet_id"] == "wallet-2" for item in paid_requests)

        credentials = await reveal_claim_credentials(claim.claim_token)
        assert credentials.agent_id
        assert credentials.business_id
        assert credentials.api_key

        session = await get_agent_session(world.id, credentials.api_key)
        assert session.agent.display_name == "bot-merchant"
        assert session.business.display_name == "bot-merchant"
        assert session.current_epoch.epoch_number == 1

    asyncio.run(_run())


def test_submit_action_and_resolve_epoch(monkeypatch):
    async def fake_create_invoice(*args, **kwargs):
        return SimpleNamespace(payment_hash="hash-claim-2", bolt11="lnbc1markettown2")

    async def fake_pay_tribute(*args, **kwargs):
        return None

    async def _run():
        monkeypatch.setattr("market_town.services.create_invoice", fake_create_invoice)
        monkeypatch.setattr("market_town.services.pay_tribute", fake_pay_tribute)

        world = await ensure_world_bootstrap(
            uuid4().hex,
            CreateWorld(name="Market Gamma", wallet_id="wallet-3"),
        )
        districts = await list_districts(world.id)
        business_types = await list_business_types(world.id)
        claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="resolver-bot",
                district_id=districts[0].id,
                business_type_id=business_types[0].id,
                payout_lnaddress="resolver@example.com",
            )
        )
        await payment_received_for_claim(
            SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
        )
        credentials = await reveal_claim_credentials(claim.claim_token)
        session = await get_agent_session(world.id, credentials.api_key)

        accepted = await submit_action(
            world.id,
            credentials.api_key,
            ActionPayload(
                epoch=session.current_epoch.epoch_number,
                business_id=session.business.id,
                price_sat=220,
                restock_units=40,
                maintenance_budget_sat=6,
                quality_budget_sat=5,
            ),
        )
        assert accepted.accepted is True
        assert accepted.replaced_previous is False

        resolved = await resolve_epoch(world.id, session.current_epoch.epoch_number)
        assert resolved.status == "resolved"
        assert resolved.digest_text

        resolved_again = await resolve_epoch(world.id, session.current_epoch.epoch_number)
        assert resolved_again.id == resolved.id
        assert resolved_again.resolved_at == resolved.resolved_at

        snapshots = await list_snapshots_for_business(session.business.id)
        assert len(snapshots) >= 1
        assert snapshots[0].epoch_number == session.current_epoch.epoch_number

        public_state = await build_public_world_state(world.id)
        assert public_state.world.id == world.id
        assert len(public_state.businesses) >= 1

    asyncio.run(_run())
