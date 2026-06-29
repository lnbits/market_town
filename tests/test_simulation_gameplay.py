import asyncio

from market_town.crud import (  # type: ignore[import]
    create_snapshot,
    get_effective_submission_for_epoch,
    get_epoch,
    list_businesses,
    list_snapshots_for_business,
    update_epoch,
)
from market_town.services import build_public_world_state, resolve_epoch  # type: ignore[import]

from .simulation_helpers import (
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
