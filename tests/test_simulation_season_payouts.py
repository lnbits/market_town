import asyncio
import json
from types import SimpleNamespace

from market_town.crud import (  # type: ignore[import]
    get_agent,
    get_payment_request,
    list_agents,
    list_businesses,
    list_season_results,
)
from market_town.models import Agent, ClaimBusinessRequest, CreateSeasonSponsorship, LeaderboardEntry, SeasonResult, World
from market_town.services import (  # type: ignore[import]
    _settle_single_season_payout,
    build_public_world_state,
    create_business_claim,
    create_season_sponsorship,
    get_agent_session,
    payment_received_for_claim,
    payment_received_for_sponsorship,
    resolve_epoch,
    retry_season_payouts,
    reveal_claim_credentials,
)

from .simulation_helpers import (
    advance_world_to_epoch,
    bootstrap_world,
    create_paid_agent,
    default_claim_options,
    ensure_epoch,
    patch_lightning,
    submit_strategy,
)


def test_claim_fee_payouts_are_recorded_and_settled(monkeypatch):
    async def _run():
        calls = patch_lightning(monkeypatch)
        world = await bootstrap_world(
            name="Fee Payout Market",
            wallet_id="fee-world-wallet",
            fee_wallet_id="fee-operator-wallet",
            operator_fee_percent=10,
        )
        district, business_type = await default_claim_options(world.id)
        claims = []

        for index in range(3):
            claim = await create_business_claim(
                ClaimBusinessRequest(
                    world_id=world.id,
                    display_name=f"fee-agent-{index}",
                    district_id=district.id,
                    business_type_id=business_type.id,
                    payout_lnaddress=f"fee-agent-{index}@example.com",
                )
            )
            claims.append(claim)
            paid = await payment_received_for_claim(
                SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
            )
            assert paid is True
            credentials = await reveal_claim_credentials(claim.claim_token)
            assert credentials.api_key

        payment_records = [await get_payment_request(claim.payment_request_id) for claim in claims]
        assert all(record is not None for record in payment_records)
        for record in payment_records:
            assert record is not None
            assert record.status == "paid"
            assert record.amount_sat == business_type.open_fee_sat
            assert record.operations_amount_sat == 50
            assert record.lnbits_tribute_amount_sat == 10
            assert record.prize_pool_amount_sat == 440
            assert (
                record.operations_amount_sat + record.lnbits_tribute_amount_sat + record.prize_pool_amount_sat
                == record.amount_sat
            )

        operator_payments = [item for item in calls.paid_invoices if item["wallet_id"] == world.wallet_id]
        operator_invoices = [item for item in calls.created_invoices if item["wallet_id"] == world.fee_wallet_id]
        assert len(operator_invoices) == len(claims)
        assert len(operator_payments) == len(claims)
        assert all(item["max_sat"] == 50 for item in operator_payments)
        assert calls.tributes == [
            {"tribute": 10, "wallet_id": world.wallet_id},
            {"tribute": 10, "wallet_id": world.wallet_id},
            {"tribute": 10, "wallet_id": world.wallet_id},
        ]

    asyncio.run(_run())


def test_season_result_is_created_after_final_epoch_and_reward_payouts_are_paid(monkeypatch):
    async def _run():
        calls = patch_lightning(monkeypatch)
        world = await bootstrap_world(
            name="Season Market",
            wallet_id="season-wallet",
            fee_wallet_id=None,
            season_length_epochs=2,
        )
        district, business_type = await default_claim_options(world.id)
        agents = []
        for index in range(3):
            claim = await create_business_claim(
                ClaimBusinessRequest(
                    world_id=world.id,
                    display_name=f"season-agent-{index}",
                    district_id=district.id,
                    business_type_id=business_type.id,
                    payout_lnaddress=f"season-agent-{index}@example.com",
                )
            )
            await payment_received_for_claim(
                SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
            )
            agents.append(await reveal_claim_credentials(claim.claim_token))

        sponsorship = await create_season_sponsorship(
            world.id, CreateSeasonSponsorship(amount_sat=50_000, sponsor_name="ACME")
        )
        assert await payment_received_for_sponsorship(
            SimpleNamespace(payment_hash=sponsorship.payment_hash, extra={"tag": "market_town_sponsorship"})
        )

        first_epoch = 1
        for index, agent in enumerate(agents):
            await submit_strategy(
                world.id,
                SimpleNamespace(api_key=agent.api_key, business_id=agent.business_id),
                epoch_number=first_epoch,
                price_sat=180 + (index * 20),
            )

        resolved_first = await resolve_epoch(world.id, first_epoch)
        assert resolved_first.status == "resolved"
        assert await list_season_results(world.id) == []

        second_epoch = 2
        await ensure_epoch(world, second_epoch)
        resolved_second = await resolve_epoch(world.id, second_epoch)
        assert resolved_second.status == "resolved"

        season_results = await list_season_results(world.id)
        assert len(season_results) == 1
        season_result = season_results[0]
        assert season_result.season_number == 1
        assert season_result.epoch_start == 1
        assert season_result.epoch_end == 2
        assert season_result.payout_status == "paid"
        assert season_result.payout_summary_text is not None
        payout_summary = json.loads(season_result.payout_summary_text)
        assert payout_summary["scheme"] == "top_3_60_30_10"
        assert payout_summary["prize_pool_sat"] == 51320
        assert [item["amount_sat"] for item in payout_summary["payouts"]] == [30792, 15396, 5132]
        assert all(item["status"] == "paid" for item in payout_summary["payouts"])

        leaderboard = json.loads(season_result.leaderboard_text)
        assert leaderboard
        assert all(item["business_id"] for item in leaderboard)
        assert all("cash_sat" in item for item in leaderboard)
        season_payouts = [item for item in calls.paid_invoices if item.get("tag") == "market_town_season_payout"]
        assert [item["max_sat"] for item in season_payouts] == [30792, 15396, 5132]

        businesses = await list_businesses(world.id)
        assert all(item.status == "closed" for item in businesses)
        public_state = await build_public_world_state(world.id)
        assert public_state.current_epoch is None
        assert public_state.world.current_epoch_number == 2
        assert public_state.world.current_season_number == 1
        for agent in agents:
            stored_agent = await get_agent(agent.agent_id)
            assert stored_agent is not None
            assert stored_agent.status == "inactive"
            try:
                await get_agent_session(world.id, agent.api_key)
                raise AssertionError("retired agent could still access the season")
            except ValueError as exc:
                assert str(exc) == "Invalid API key."

        reopening_agent = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="season-agent-reopened",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="season-agent-reopened@example.com",
            )
        )
        await payment_received_for_claim(
            SimpleNamespace(payment_hash=reopening_agent.payment_hash, extra={"tag": "market_town"})
        )
        credentials = await reveal_claim_credentials(reopening_agent.claim_token)
        session = await get_agent_session(world.id, credentials.api_key)
        assert session.current_epoch.epoch_number == 3
        assert session.current_epoch.season_number == 2

    asyncio.run(_run())


def test_partial_season_payouts_retry_without_double_paying(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(
            name="Season Retry Market",
            wallet_id="season-retry-wallet",
            fee_wallet_id=None,
            season_length_epochs=2,
        )
        district, business_type = await default_claim_options(world.id)
        agents = []
        for index in range(3):
            claim = await create_business_claim(
                ClaimBusinessRequest(
                    world_id=world.id,
                    display_name=f"retry-season-agent-{index}",
                    district_id=district.id,
                    business_type_id=business_type.id,
                    payout_lnaddress=f"retry-season-agent-{index}@example.com",
                )
            )
            await payment_received_for_claim(
                SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
            )
            agents.append(await reveal_claim_credentials(claim.claim_token))

        successful_payout_amounts: list[int] = []
        payout_attempts: list[int] = []
        failed_once = False

        async def flaky_pay_invoice(**kwargs):
            nonlocal failed_once
            payout_attempts.append(kwargs["max_sat"])
            if kwargs.get("tag") == "market_town_season_payout" and kwargs["max_sat"] == 396:
                if not failed_once:
                    failed_once = True
                    return SimpleNamespace(status="pending", pending=True, failed=False, payment_hash="pending-396")
            successful_payout_amounts.append(kwargs["max_sat"])
            return SimpleNamespace(status="success", pending=False, failed=False, payment_hash=f"paid-{len(successful_payout_amounts)}")

        async def keep_pending(payment):
            return payment

        monkeypatch.setattr("market_town.services.pay_invoice", flaky_pay_invoice)
        monkeypatch.setattr("market_town.services.update_pending_payment", keep_pending)

        for index, agent in enumerate(agents):
            await submit_strategy(
                world.id,
                SimpleNamespace(api_key=agent.api_key, business_id=agent.business_id),
                epoch_number=1,
                price_sat=180 + (index * 20),
            )

        resolved_first = await resolve_epoch(world.id, 1)
        assert resolved_first.status == "resolved"

        await ensure_epoch(world, 2)
        resolved_second = await resolve_epoch(world.id, 2)
        assert resolved_second.status == "resolved"

        season_results = await list_season_results(world.id)
        assert len(season_results) == 1
        season_result = season_results[0]
        assert season_result.payout_status == "partial"
        assert season_result.payout_summary_text is not None
        payout_summary = json.loads(season_result.payout_summary_text)
        assert sorted(item["status"] for item in payout_summary["payouts"]) == [
            "failed",
            "paid",
            "paid",
        ]

        retry = await resolve_epoch(world.id, 2)
        assert retry.status == "resolved"

        season_results = await list_season_results(world.id)
        assert len(season_results) == 1
        season_result = season_results[0]
        assert season_result.payout_status == "paid"
        assert season_result.payout_summary_text is not None
        payout_summary = json.loads(season_result.payout_summary_text)
        assert [item["status"] for item in payout_summary["payouts"]] == [
            "paid",
            "paid",
            "paid",
        ]
        assert payout_attempts.count(396) == 2
        assert payout_attempts.count(792) == 1
        assert payout_attempts.count(132) == 1
        assert successful_payout_amounts == [792, 132, 396]
        assert successful_payout_amounts.count(792) == 1
        assert successful_payout_amounts.count(396) == 1
        assert successful_payout_amounts.count(132) == 1

    asyncio.run(_run())


def test_pending_season_payout_refreshes_before_marking_failed(monkeypatch):
    async def _run():
        world = World(id="world", user_id="user", name="World", wallet_id="wallet", world_seed="seed")
        season_result = SeasonResult(
            id="season",
            world_id=world.id,
            season_number=1,
            epoch_start=1,
            epoch_end=1,
            leaderboard_text="[]",
        )
        agent = Agent(
            id="agent",
            world_id=world.id,
            display_name="Agent",
            api_key_hash="hash",
            payout_lnaddress="agent@example.com",
        )
        refreshed = []

        async def fake_get_pr_from_lnurl(*_args, **_kwargs):
            return "lnbc1pending"

        async def fake_pay_invoice(**_kwargs):
            return SimpleNamespace(status="pending", pending=True, failed=False, payment_hash="hash")

        async def fake_update_pending_payment(payment):
            refreshed.append(payment.payment_hash)
            return SimpleNamespace(status="success", pending=False, failed=False, payment_hash=payment.payment_hash)

        monkeypatch.setattr("market_town.services.get_pr_from_lnurl", fake_get_pr_from_lnurl)
        monkeypatch.setattr("market_town.services.pay_invoice", fake_pay_invoice)
        monkeypatch.setattr("market_town.services.update_pending_payment", fake_update_pending_payment)

        payout = await _settle_single_season_payout(world, season_result, "business", 21, agent)

        assert refreshed == ["hash"]
        assert payout["status"] == "paid"
        assert payout["payment_hash"] == "hash"

    asyncio.run(_run())


def test_retry_failed_season_payout_uses_existing_summary_amounts(monkeypatch):
    async def _run():
        world = World(
            id="retry-world",
            user_id="user",
            name="Retry World",
            wallet_id="wallet",
            world_seed="seed",
            season_length_epochs=2,
        )
        leaderboard = [
            LeaderboardEntry(
                business_id="business-1",
                agent_id="agent-1",
                business_name="Business 1",
                district_name="District",
            )
        ]
        season_result = SeasonResult(
            id="season-1",
            world_id=world.id,
            season_number=1,
            epoch_start=1,
            epoch_end=2,
            leaderboard_text=json.dumps([item.dict() for item in leaderboard]),
            payout_status="failed",
            payout_summary_text=json.dumps(
                {
                    "scheme": "top_3_60_30_10",
                    "prize_pool_sat": 100,
                    "payment_request_ids": ["old-request"],
                    "payouts": [
                        {
                            "business_id": "business-1",
                            "agent_id": "agent-1",
                            "amount_sat": 100,
                            "status": "failed",
                            "payment_hash": None,
                            "error": "Payment status is pending.",
                        }
                    ],
                }
            ),
        )
        paid_amounts = []

        async def fake_pay_invoice(**kwargs):
            paid_amounts.append(kwargs["max_sat"])
            return SimpleNamespace(status="success", pending=False, failed=False, payment_hash="paid-retry")

        async def fake_update(updated):
            return updated

        async def fake_get_season_result(*_args):
            return season_result

        async def fake_no_paid_requests(*_args, **_kwargs):
            return []

        async def fake_businesses(*_args):
            return [SimpleNamespace(id="business-1", agent_id="agent-1")]

        async def fake_agents(*_args):
            return [
                Agent(
                    id="agent-1",
                    world_id=world.id,
                    display_name="Agent",
                    api_key_hash="hash",
                    payout_lnaddress="agent@example.com",
                )
            ]

        async def fake_get_pr_from_lnurl(*_args, **_kwargs):
            return "lnbc1retry"

        async def fake_audit(*_args, **_kwargs):
            return None

        monkeypatch.setattr("market_town.services.get_season_result", fake_get_season_result)
        monkeypatch.setattr("market_town.services.list_paid_payment_requests_for_season", fake_no_paid_requests)
        monkeypatch.setattr("market_town.services.list_businesses", fake_businesses)
        monkeypatch.setattr("market_town.services.list_agents", fake_agents)
        monkeypatch.setattr("market_town.services.get_pr_from_lnurl", fake_get_pr_from_lnurl)
        monkeypatch.setattr("market_town.services.pay_invoice", fake_pay_invoice)
        monkeypatch.setattr("market_town.services.update_season_result", fake_update)
        monkeypatch.setattr("market_town.services.create_audit_event", fake_audit)

        updated = await retry_season_payouts(world, 1)

        assert paid_amounts == [100]
        assert updated.payout_status == "paid"
        summary = json.loads(updated.payout_summary_text)
        assert summary["prize_pool_sat"] == 100
        assert summary["payment_request_ids"] == ["old-request"]
        assert summary["payouts"][0]["status"] == "paid"

    asyncio.run(_run())


def test_full_season_lifecycle_archives_agents_and_reopens_next_epoch(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(
            name="Lifecycle Market",
            wallet_id="lifecycle-wallet",
            fee_wallet_id=None,
            season_length_epochs=2,
        )
        district, business_type = await default_claim_options(world.id)
        agents = [
            await create_paid_agent(
                world,
                display_name=f"lifecycle-agent-{index}",
                district_id=district.id,
                business_type_id=business_type.id,
            )
            for index in range(3)
        ]

        session = await get_agent_session(world.id, agents[0].api_key)
        assert session.current_epoch.epoch_number == 1
        assert session.current_epoch.season_number == 1

        for epoch_number in (1, 2):
            if epoch_number > 1:
                world = await advance_world_to_epoch(world, epoch_number)
                await ensure_epoch(world, epoch_number)
            for index, agent in enumerate(agents):
                accepted = await submit_strategy(
                    world.id,
                    agent,
                    epoch_number=epoch_number,
                    price_sat=180 + (index * 20),
                    restock_units=30 + index,
                )
                assert accepted.accepted is True
            resolved = await resolve_epoch(world.id, epoch_number)
            assert resolved.status == "resolved"
            assert resolved.epoch_number == epoch_number
            assert resolved.season_number == 1

        season_results = await list_season_results(world.id)
        assert [item.season_number for item in season_results] == [1]

        stored_agents = await list_agents(world.id)
        assert len(stored_agents) == 3
        assert all(item.status == "inactive" for item in stored_agents)
        stored_businesses = await list_businesses(world.id)
        assert len(stored_businesses) == 3
        assert all(item.status == "closed" for item in stored_businesses)
        assert all(item.closed_at is not None for item in stored_businesses)

        public_state = await build_public_world_state(world.id)
        public_district = next(item for item in public_state.districts if item.id == district.id)
        assert public_state.current_epoch is None
        assert public_state.world.current_epoch_number == 2
        assert public_state.world.current_season_number == 1
        assert public_district.occupied_slots == 0
        assert public_district.available_slots == public_district.slot_limit

        for agent in agents:
            try:
                await submit_strategy(world.id, agent, epoch_number=3)
                raise AssertionError("retired agent submitted into the next season")
            except ValueError as exc:
                assert str(exc) == "Invalid API key."

        reopened = await create_paid_agent(
            world,
            display_name="lifecycle-agent-reopened",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        reopened_session = await get_agent_session(world.id, reopened.api_key)
        assert reopened_session.current_epoch.epoch_number == 3
        assert reopened_session.current_epoch.season_number == 2

        public_state = await build_public_world_state(world.id)
        public_district = next(item for item in public_state.districts if item.id == district.id)
        assert public_state.current_epoch is not None
        assert public_state.current_epoch.epoch_number == 3
        assert public_state.current_epoch.season_number == 2
        assert public_district.occupied_slots == 1
        assert public_district.available_slots == public_district.slot_limit - 1
        assert len(await list_agents(world.id)) == 4
        assert len(await list_businesses(world.id)) == 4

        for epoch_number in (3, 4):
            if epoch_number > 3:
                world = await advance_world_to_epoch(world, epoch_number)
                await ensure_epoch(world, epoch_number)
            accepted = await submit_strategy(
                world.id,
                reopened,
                epoch_number=epoch_number,
                price_sat=210,
                restock_units=35,
            )
            assert accepted.accepted is True
            resolved = await resolve_epoch(world.id, epoch_number)
            assert resolved.status == "resolved"
            assert resolved.epoch_number == epoch_number
            assert resolved.season_number == 2

        season_results = await list_season_results(world.id)
        assert [item.season_number for item in season_results] == [2, 1]
        stored_reopened_agent = await get_agent(reopened.agent_id)
        assert stored_reopened_agent is not None
        assert stored_reopened_agent.status == "inactive"

    asyncio.run(_run())
