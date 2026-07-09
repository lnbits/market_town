import asyncio
from types import SimpleNamespace

from market_town.crud import get_season_sponsorship  # type: ignore[import]
from market_town.models import CreateSeasonSponsorship  # type: ignore[import]
from market_town.services import (  # type: ignore[import]
    build_public_world_state,
    create_season_sponsorship,
    get_season_sponsorship_status,
    payment_received_for_sponsorship,
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


def test_create_season_sponsorship_invoice_full_amount_no_fees(monkeypatch):
    async def _run():
        calls = patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Sponsor Market", wallet_id="sponsor-wallet")

        response = await create_season_sponsorship(
            world.id,
            CreateSeasonSponsorship(amount_sat=10_000, sponsor_name="Alice"),
        )

        assert response.amount_sat == 10_000
        assert response.status == "pending"
        assert response.payment_request
        # Idle worlds sponsor the next season (1), not current_season_number (0)
        assert response.season_number == 1

        sponsorship_invoice = next(
            item
            for item in calls.created_invoices
            if item.get("extra", {}).get("tag") == "market_town_sponsorship"
        )
        assert sponsorship_invoice["wallet_id"] == world.wallet_id
        assert sponsorship_invoice["amount"] == 10_000
        assert sponsorship_invoice["extra"]["world_id"] == world.id
        assert (
            sponsorship_invoice["extra"]["season_number"] == 1
        )  # Next season for idle world
        assert sponsorship_invoice["extra"]["sponsorship_id"] == response.sponsorship_id
        assert sponsorship_invoice["extra"]["sponsor_name"] == "Alice"

        assert not any(
            item["wallet_id"] == world.fee_wallet_id for item in calls.created_invoices
        )
        assert calls.tributes == []

    asyncio.run(_run())


def test_paid_sponsorship_counts_in_public_state_and_hides_small_sponsors(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(
            name="Public Sponsor Market", wallet_id="public-sponsor-wallet"
        )

        small = await create_season_sponsorship(
            world.id,
            CreateSeasonSponsorship(amount_sat=9_999, sponsor_name="Small Fry"),
        )
        large = await create_season_sponsorship(
            world.id,
            CreateSeasonSponsorship(amount_sat=75_000, sponsor_name="Big Spender"),
        )
        anonymous = await create_season_sponsorship(
            world.id,
            CreateSeasonSponsorship(amount_sat=10_000, sponsor_name=None),
        )

        for sponsorship in (small, large, anonymous):
            paid = await payment_received_for_sponsorship(
                SimpleNamespace(
                    payment_hash=sponsorship.payment_hash,
                    extra={"tag": "market_town_sponsorship"},
                )
            )
            assert paid is True

        public_state = await build_public_world_state(world.id)
        assert public_state.sponsorship_total_sat == 94_999
        names = [sponsor.name for sponsor in public_state.public_sponsors]
        assert "Big Spender" in names
        assert "Small Fry" not in names
        assert anonymous.sponsorship_id not in [
            sponsor.name for sponsor in public_state.public_sponsors
        ]

    asyncio.run(_run())


def test_season_payout_includes_sponsorship_total_with_existing_split(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(
            name="Sponsored Payout Market",
            wallet_id="sponsored-payout-wallet",
            fee_wallet_id=None,
            season_length_epochs=2,
        )
        district, business_type = await default_claim_options(world.id)
        agents = [
            await create_paid_agent(
                world,
                display_name=f"sponsored-agent-{index}",
                district_id=district.id,
                business_type_id=business_type.id,
            )
            for index in range(3)
        ]

        sponsorship = await create_season_sponsorship(
            world.id,
            CreateSeasonSponsorship(amount_sat=1_000, sponsor_name="Boost"),
        )
        await payment_received_for_sponsorship(
            SimpleNamespace(
                payment_hash=sponsorship.payment_hash,
                extra={"tag": "market_town_sponsorship"},
            )
        )

        for index, agent in enumerate(agents):
            await submit_strategy(
                world.id,
                agent,
                epoch_number=1,
                price_sat=180 + (index * 20),
            )

        await ensure_epoch(world, 2)
        from market_town.services import resolve_epoch

        resolved_first = await resolve_epoch(world.id, 1)
        assert resolved_first.status == "resolved"
        resolved_second = await resolve_epoch(world.id, 2)
        assert resolved_second.status == "resolved"

        from market_town.crud import list_season_results

        season_results = await list_season_results(world.id)
        assert len(season_results) == 1
        summary = __import__("json").loads(season_results[0].payout_summary_text)
        assert summary["prize_pool_sat"] == 1320 + 1000
        assert [item["amount_sat"] for item in summary["payouts"]] == [1392, 696, 232]

    asyncio.run(_run())


def test_invoice_listener_marks_sponsorship_paid(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(
            name="Listener Market", wallet_id="listener-wallet"
        )

        response = await create_season_sponsorship(
            world.id,
            CreateSeasonSponsorship(amount_sat=10_000, sponsor_name="Listener"),
        )

        paid = await payment_received_for_sponsorship(
            SimpleNamespace(
                payment_hash=response.payment_hash,
                extra={"tag": "market_town_sponsorship"},
            )
        )
        assert paid is True

        stored = await get_season_sponsorship(response.sponsorship_id)
        assert stored is not None
        assert stored.status == "paid"
        assert stored.paid_at is not None

        status = await get_season_sponsorship_status(response.sponsorship_id)
        assert status.status == "paid"

    asyncio.run(_run())
