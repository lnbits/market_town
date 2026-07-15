import asyncio

from market_town.crud import (  # type: ignore[import]
    create_snapshot,
    get_business,
    get_effective_submission_for_epoch,
    get_epoch,
    list_businesses,
    list_season_results,
    list_snapshots_for_business,
    update_business,
    update_epoch,
)
from market_town.models import BusinessEpochSnapshot  # type: ignore[import]
from market_town.services import build_public_world_state, resolve_epoch  # type: ignore[import]

from .simulation_helpers import (
    advance_world_to_epoch,
    bootstrap_world,
    create_paid_agent,
    current_session,
    default_claim_options,
    ensure_epoch,
    patch_lightning,
    submit_strategy,
)


def test_multiple_agents_join_play_and_epoch_resolves(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Gameplay Market")
        district, business_type = await default_claim_options(world.id)
        agents = [
            await create_paid_agent(
                world,
                display_name=f"agent-{index}",
                district_id=district.id,
                business_type_id=business_type.id,
            )
            for index in range(3)
        ]

        session = await current_session(world.id, agents[0])
        epoch_number = session.current_epoch.epoch_number
        for index, agent in enumerate(agents):
            accepted = await submit_strategy(
                world.id,
                agent,
                epoch_number=epoch_number,
                price_sat=180 + (index * 20),
                restock_units=45,
                maintenance_budget_sat=5 + index,
                quality_budget_sat=4 + index,
            )
            assert accepted.accepted is True

        resolved = await resolve_epoch(world.id, epoch_number)
        assert resolved.status == "resolved"
        assert resolved.digest_text

        businesses = await list_businesses(world.id)
        assert len(businesses) == 3
        assert all(item.status == "active" for item in businesses)

        for agent in agents:
            snapshots = await list_snapshots_for_business(agent.business_id)
            assert len(snapshots) == 1
            assert snapshots[0].epoch_number == epoch_number

        public_state = await build_public_world_state(world.id)
        assert len(public_state.businesses) == 3
        assert public_state.leaderboard
        assert any(item.reputation > 0 for item in public_state.leaderboard)

    asyncio.run(_run())


def test_single_business_price_reduces_sales(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Single Business Pricing Market")
        district, business_type = await default_claim_options(world.id)
        agent = await create_paid_agent(
            world,
            display_name="price-sensitive-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )

        first_epoch = (await current_session(world.id, agent)).current_epoch.epoch_number
        await submit_strategy(
            world.id,
            agent,
            epoch_number=first_epoch,
            price_sat=160,
            restock_units=48,
            maintenance_budget_sat=0,
            quality_budget_sat=0,
        )
        await resolve_epoch(world.id, first_epoch)
        normal_snapshot = (await list_snapshots_for_business(agent.business_id))[0]

        world = await advance_world_to_epoch(world, first_epoch + 1)
        await ensure_epoch(world, first_epoch + 1)
        accepted = await submit_strategy(
            world.id,
            agent,
            epoch_number=first_epoch + 1,
            price_sat=2_800,
            restock_units=48,
            maintenance_budget_sat=0,
            quality_budget_sat=0,
        )
        assert accepted.accepted is True
        await resolve_epoch(world.id, first_epoch + 1)
        high_price_snapshot = (await list_snapshots_for_business(agent.business_id))[0]

        assert high_price_snapshot.units_sold * 2 <= normal_snapshot.units_sold

    asyncio.run(_run())


def test_snapshot_profit_matches_cash_change(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Net Profit Market")
        district, business_type = await default_claim_options(world.id)
        agent = await create_paid_agent(
            world,
            display_name="net-profit-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        epoch_number = (await current_session(world.id, agent)).current_epoch.epoch_number
        await submit_strategy(
            world.id,
            agent,
            epoch_number=epoch_number,
            price_sat=160,
            restock_units=12,
            maintenance_budget_sat=0,
            quality_budget_sat=0,
        )
        await resolve_epoch(world.id, epoch_number)
        snapshot = (await list_snapshots_for_business(agent.business_id))[0]

        assert snapshot.profit_sat == snapshot.cash_after - snapshot.cash_before

    asyncio.run(_run())


def test_public_digests_show_epoch_event(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Event Digest Market")
        epoch = await ensure_epoch(world, 1)
        await update_epoch(epoch.copy(update={"status": "resolved", "event_summary_text": "Festival Day"}))

        public_state = await build_public_world_state(world.id)
        assert public_state.recent_digests[0].active_event_name == "Festival Day"

    asyncio.run(_run())


def test_leaderboard_ranks_by_season_performance_score_not_cash(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Fair Leaderboard Market", season_length_epochs=4)
        district, business_type = await default_claim_options(world.id)
        early_agent = await create_paid_agent(
            world,
            display_name="early-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        late_agent = await create_paid_agent(
            world,
            display_name="late-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )

        early_business = await get_business(early_agent.business_id)
        late_business = await get_business(late_agent.business_id)
        assert early_business is not None
        assert late_business is not None

        await update_business(early_business.copy(update={"cash_sat": 1000, "reputation": 0.5}))
        await update_business(late_business.copy(update={"cash_sat": 200, "reputation": 0.5}))

        for epoch_number, profit in [(1, 40), (2, 40), (3, 40)]:
            await create_snapshot(
                BusinessEpochSnapshot(
                    id=f"early-{epoch_number}",
                    world_id=world.id,
                    epoch_number=epoch_number,
                    business_id=early_agent.business_id,
                    profit_sat=profit,
                    revenue_sat=profit,
                    cash_before=1000 - profit,
                    cash_after=1000,
                )
            )
        await create_snapshot(
            BusinessEpochSnapshot(
                id="late-3",
                world_id=world.id,
                epoch_number=3,
                business_id=late_agent.business_id,
                profit_sat=220,
                revenue_sat=220,
                cash_before=-20,
                cash_after=200,
            )
        )

        public_state = await build_public_world_state(world.id)
        assert [entry.business_name for entry in public_state.leaderboard[:2]] == [
            "late-agent",
            "early-agent",
        ]
        assert public_state.leaderboard[0].score > public_state.leaderboard[1].score
        assert public_state.leaderboard[0].active_epoch_count == 1
        assert public_state.leaderboard[0].average_profit_sat == 220

    asyncio.run(_run())


def test_latest_valid_submission_wins_and_missing_submission_falls_back(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Fallback Market")
        district, business_type = await default_claim_options(world.id)
        active_agent = await create_paid_agent(
            world,
            display_name="active-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        idle_agent = await create_paid_agent(
            world,
            display_name="idle-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )

        session = await current_session(world.id, active_agent)
        epoch_number = session.current_epoch.epoch_number
        first = await submit_strategy(
            world.id,
            active_agent,
            epoch_number=epoch_number,
            price_sat=250,
            restock_units=20,
        )
        second = await submit_strategy(
            world.id,
            active_agent,
            epoch_number=epoch_number,
            price_sat=175,
            restock_units=50,
        )
        assert first.accepted is True
        assert second.accepted is True
        assert second.replaced_previous is True

        effective = await get_effective_submission_for_epoch(world.id, epoch_number, active_agent.business_id)
        assert effective is not None
        assert effective.payload.price_sat == 175
        assert effective.payload.restock_units == 50

        resolved = await resolve_epoch(world.id, epoch_number)
        assert resolved.status == "resolved"

        active_snapshots = await list_snapshots_for_business(active_agent.business_id)
        idle_snapshots = await list_snapshots_for_business(idle_agent.business_id)
        assert active_snapshots[0].stock_before == 0
        assert idle_snapshots[0].stock_before == 0

        businesses = {item.id: item for item in await list_businesses(world.id)}
        assert businesses[active_agent.business_id].price_sat == 175
        assert businesses[idle_agent.business_id].missed_epochs == 1

        await ensure_epoch(world, epoch_number + 1)

    asyncio.run(_run())


def test_partial_epoch_snapshot_retry_fails_fast(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Partial Snapshot Market")
        district, business_type = await default_claim_options(world.id)
        agents = [
            await create_paid_agent(
                world,
                display_name=f"partial-agent-{index}",
                district_id=district.id,
                business_type_id=business_type.id,
            )
            for index in range(3)
        ]

        session = await current_session(world.id, agents[0])
        epoch_number = session.current_epoch.epoch_number
        for index, agent in enumerate(agents):
            accepted = await submit_strategy(
                world.id,
                agent,
                epoch_number=epoch_number,
                price_sat=190 + (index * 10),
                restock_units=30,
            )
            assert accepted.accepted is True

        snapshot_calls = 0
        original_create_snapshot = create_snapshot

        async def flaky_create_snapshot(snapshot):
            nonlocal snapshot_calls
            snapshot_calls += 1
            if snapshot_calls == 2:
                raise ValueError("snapshot write failed")
            return await original_create_snapshot(snapshot)

        monkeypatch.setattr("market_town.services.create_snapshot", flaky_create_snapshot)

        try:
            await resolve_epoch(world.id, epoch_number)
            raise AssertionError("partial resolution unexpectedly succeeded")
        except ValueError as exc:
            assert str(exc) == "snapshot write failed"

        epoch = await get_epoch(world.id, epoch_number)
        assert epoch is not None
        await update_epoch(epoch.copy(update={"status": "open"}))

        try:
            await resolve_epoch(world.id, epoch_number)
            raise AssertionError("partial snapshot retry unexpectedly succeeded")
        except ValueError as exc:
            assert str(exc) == "Epoch resolution already has partial snapshots."

        assert snapshot_calls == 2
        snapshot_counts = [len(await list_snapshots_for_business(agent.business_id)) for agent in agents]
        assert sum(snapshot_counts) == 1

    asyncio.run(_run())


def test_submitted_reasoning_is_stored(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Reasoning Storage Market")
        district, business_type = await default_claim_options(world.id)
        agent = await create_paid_agent(
            world,
            display_name="reasoning-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        session = await current_session(world.id, agent)
        epoch_number = session.current_epoch.epoch_number
        await submit_strategy(
            world.id,
            agent,
            epoch_number=epoch_number,
            price_sat=200,
            reasoning="Undercut competitors and restock heavily.",
        )
        effective = await get_effective_submission_for_epoch(world.id, epoch_number, agent.business_id)
        assert effective is not None
        assert effective.payload.reasoning == "Undercut competitors and restock heavily."

    asyncio.run(_run())


def test_public_state_shows_only_delayed_reasoning(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Delayed Reasoning Market")
        district, business_type = await default_claim_options(world.id)
        agent = await create_paid_agent(
            world,
            display_name="delayed-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        session = await current_session(world.id, agent)
        epoch_number = session.current_epoch.epoch_number
        await submit_strategy(
            world.id,
            agent,
            epoch_number=epoch_number,
            price_sat=200,
            reasoning="First epoch reasoning.",
        )

        public_state = await build_public_world_state(world.id)
        assert public_state.delayed_reasoning == []

        await ensure_epoch(world, epoch_number + 1)
        await ensure_epoch(world, epoch_number + 2)
        await advance_world_to_epoch(world, epoch_number + 2)

        public_state = await build_public_world_state(world.id)
        assert len(public_state.delayed_reasoning) == 1
        assert public_state.delayed_reasoning[0].reasoning == "First epoch reasoning."
        assert public_state.delayed_reasoning[0].business_name == "delayed-agent"
        assert public_state.delayed_reasoning[0].epoch_number == epoch_number

    asyncio.run(_run())


def test_public_payload_excludes_secrets(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Secret Safe Market")
        district, business_type = await default_claim_options(world.id)
        agent = await create_paid_agent(
            world,
            display_name="secret-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        session = await current_session(world.id, agent)
        await submit_strategy(
            world.id,
            agent,
            epoch_number=session.current_epoch.epoch_number,
            price_sat=200,
            reasoning="Public reasoning.",
        )

        public_state = await build_public_world_state(world.id)
        payload = public_state.json()
        assert agent.api_key not in payload
        assert "claim_token" not in payload
        assert "payment_request" not in payload
        assert "api_key" not in payload
        assert "issued_api_key" not in payload

    asyncio.run(_run())


def test_public_state_defaults_to_current_season_and_excludes_old_closed_businesses(
    monkeypatch,
):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Season Filter Market", season_length_epochs=2)
        district, business_type = await default_claim_options(world.id)
        first_agents = [
            await create_paid_agent(
                world,
                display_name=f"s1-agent-{index}",
                district_id=district.id,
                business_type_id=business_type.id,
            )
            for index in range(2)
        ]

        for epoch_number in (1, 2):
            if epoch_number > 1:
                world = await advance_world_to_epoch(world, epoch_number)
                await ensure_epoch(world, epoch_number)
            for agent in first_agents:
                accepted = await submit_strategy(
                    world.id,
                    agent,
                    epoch_number=epoch_number,
                    price_sat=200,
                    restock_units=30,
                )
                assert accepted.accepted is True
            resolved = await resolve_epoch(world.id, epoch_number)
            assert resolved.status == "resolved"

        assert all(item.status == "closed" for item in await list_businesses(world.id))
        assert len(await list_season_results(world.id)) == 1

        world = await advance_world_to_epoch(world, 3)
        await ensure_epoch(world, 3)
        new_agent = await create_paid_agent(
            world,
            display_name="s2-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        accepted = await submit_strategy(
            world.id,
            new_agent,
            epoch_number=3,
            price_sat=210,
            restock_units=35,
        )
        assert accepted.accepted is True
        resolved = await resolve_epoch(world.id, 3)
        assert resolved.status == "resolved"

        public_state = await build_public_world_state(world.id)
        assert len(public_state.businesses) == 1
        assert public_state.businesses[0].business_id == new_agent.business_id
        assert len(public_state.leaderboard) == 1
        assert public_state.leaderboard[0].business_id == new_agent.business_id

        assert len(public_state.season_results) == 1
        season_result = public_state.season_results[0]
        assert season_result.season_number == 1
        old_ids = {agent.business_id for agent in first_agents}
        assert any(entry.business_id in old_ids for entry in season_result.leaderboard)

    asyncio.run(_run())
