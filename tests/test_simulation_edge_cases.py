import asyncio
from datetime import timedelta
from types import SimpleNamespace

from market_town.crud import (  # type: ignore[import]
    get_payment_request,
    get_world_by_id,
    list_agents,
    list_business_types,
    list_businesses,
    list_epochs,
    update_district,
    update_epoch,
    update_payment_request,
    update_world,
)
from market_town.models import ActionPayload, ClaimBusinessRequest
from market_town.services import (  # type: ignore[import]
    build_admin_dashboard,
    build_public_world_state,
    create_business_claim,
    ensure_current_epoch,
    get_agent_session,
    get_claim_status,
    payment_received_for_claim,
    pending_claim_cutoff,
    submit_action,
    utc_now,
)

from .simulation_helpers import (
    bootstrap_world,
    create_paid_agent,
    current_session,
    default_claim_options,
    ensure_epoch,
    patch_lightning,
    submit_strategy,
)


def test_invalid_actions_are_recorded_but_do_not_replace_valid_submission(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Invalid Action Market")
        district, business_type = await default_claim_options(world.id)
        agent = await create_paid_agent(
            world,
            display_name="validator",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        other_agent = await create_paid_agent(
            world,
            display_name="other-validator",
            district_id=district.id,
            business_type_id=business_type.id,
        )

        session = await current_session(world.id, agent)
        valid = await submit_strategy(
            world.id,
            agent,
            epoch_number=session.current_epoch.epoch_number,
            price_sat=200,
        )
        wrong_epoch = await submit_action(
            world.id,
            agent.api_key,
            ActionPayload(
                epoch=session.current_epoch.epoch_number + 1,
                business_id=agent.business_id,
                price_sat=200,
            ),
        )
        wrong_business = await submit_action(
            world.id,
            agent.api_key,
            ActionPayload(
                epoch=session.current_epoch.epoch_number,
                business_id=other_agent.business_id,
                price_sat=200,
            ),
        )

        assert valid.accepted is True
        assert wrong_epoch.accepted is False
        assert wrong_epoch.validation_error == "Submission epoch does not match the current epoch."
        assert wrong_business.accepted is False
        assert wrong_business.validation_error == "Submission business does not match the active business."

    asyncio.run(_run())


def test_ensure_current_epoch_caps_backfill_per_call(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Backfill Cap Market")
        district, business_type = await default_claim_options(world.id)
        await create_paid_agent(
            world,
            display_name="backfill-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        world = await update_world(
            world.copy(
                update={
                    "epoch_duration_hours": 1,
                    "started_at": utc_now() - timedelta(hours=12),
                }
            )
        )

        current_epoch = await ensure_current_epoch(world)
        assert current_epoch is not None
        assert current_epoch.epoch_number == 6

        refreshed_world = await get_world_by_id(world.id)
        assert refreshed_world is not None
        assert refreshed_world.current_epoch_number == 6
        epochs = await list_epochs(world.id)
        assert [item.epoch_number for item in epochs] == [6, 5, 4, 3, 2, 1]
        assert all(item.epoch_number <= 6 for item in epochs)

    asyncio.run(_run())


def test_first_business_rebases_stale_open_epoch(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Stale Epoch Market")
        district, business_type = await default_claim_options(world.id)
        world = await update_world(
            world.copy(
                update={
                    "last_resolved_epoch": 42,
                    "current_epoch_number": 42,
                    "started_at": utc_now() - timedelta(hours=4 * 43),
                }
            )
        )
        stale_epoch = await ensure_epoch(world, 43)
        await update_epoch(
            stale_epoch.copy(
                update={
                    "started_at": utc_now() - timedelta(hours=4),
                    "submission_deadline_at": utc_now() - timedelta(minutes=5),
                    "digest_at": utc_now() - timedelta(minutes=1),
                }
            )
        )

        agent = await create_paid_agent(
            world,
            display_name="first-after-idle",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        session = await current_session(world.id, agent)

        assert session.current_epoch.epoch_number == 43
        assert session.current_epoch.submission_deadline_at > utc_now()

    asyncio.run(_run())


def test_paid_claim_becomes_unclaimed_if_district_fills_before_settlement(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Full District Market")
        district, business_type = await default_claim_options(world.id)
        await update_district(district.copy(update={"slot_limit": 2}))

        first_claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="first",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="first@example.com",
            )
        )
        second_claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="second",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="second@example.com",
            )
        )
        await update_district(district.copy(update={"slot_limit": 1}))

        first_paid = await payment_received_for_claim(
            SimpleNamespace(payment_hash=first_claim.payment_hash, extra={"tag": "market_town"})
        )
        second_paid = await payment_received_for_claim(
            SimpleNamespace(payment_hash=second_claim.payment_hash, extra={"tag": "market_town"})
        )

        first_record = await get_payment_request(first_claim.payment_request_id)
        second_record = await get_payment_request(second_claim.payment_request_id)
        assert first_paid is True
        assert second_paid is False
        assert first_record is not None
        assert second_record is not None
        assert first_record.status == "paid"
        assert second_record.status == "paid_unclaimed"
        assert second_record.agent_id is None
        assert second_record.business_id is None

    asyncio.run(_run())


def test_public_district_slots_discount_active_and_pending_claims(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Slot Market")
        district, business_type = await default_claim_options(world.id)
        await update_district(district.copy(update={"slot_limit": 3}))

        paid_agent = await create_paid_agent(
            world,
            display_name="slot-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        assert paid_agent.business_id
        pending_claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="pending-slot-agent",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="pending-slot-agent@example.com",
            )
        )
        assert pending_claim.payment_request_id

        public_state = await build_public_world_state(world.id)
        public_district = next(item for item in public_state.districts if item.id == district.id)
        assert public_district.slot_limit == 3
        assert public_district.occupied_slots == 1
        assert public_district.pending_slots == 1
        assert public_district.available_slots == 1

    asyncio.run(_run())


def test_invalid_claim_inputs_are_rejected(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Bad Claim Market")
        district, business_type = await default_claim_options(world.id)
        bad_lnaddress = ClaimBusinessRequest(
            world_id=world.id,
            display_name="bad-lnaddress",
            district_id=district.id,
            business_type_id=business_type.id,
            payout_lnaddress="not-an-lnaddress",
        )
        try:
            await create_business_claim(bad_lnaddress)
            raise AssertionError("invalid LN address was accepted")
        except ValueError as exc:
            assert "Lightning address" in str(exc)

        business_types = await list_business_types(world.id)
        missing_type = ClaimBusinessRequest(
            world_id=world.id,
            display_name="bad-type",
            district_id=district.id,
            business_type_id=f"missing-{business_types[0].id}",
            payout_lnaddress="badtype@example.com",
        )
        try:
            await create_business_claim(missing_type)
            raise AssertionError("invalid business type was accepted")
        except ValueError as exc:
            assert str(exc) == "Business type not found."

    asyncio.run(_run())


def test_duplicate_active_claim_identity_is_rejected(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Duplicate Claim Market")
        district, business_type = await default_claim_options(world.id)
        await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="duplicate-agent",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="duplicate@example.com",
            )
        )

        try:
            await create_business_claim(
                ClaimBusinessRequest(
                    world_id=world.id,
                    display_name="different-agent",
                    district_id=district.id,
                    business_type_id=business_type.id,
                    payout_lnaddress="duplicate@example.com",
                )
            )
            raise AssertionError("duplicate payout address was accepted")
        except ValueError as exc:
            assert str(exc) == "A claim for this payout address is already pending."

        try:
            await create_business_claim(
                ClaimBusinessRequest(
                    world_id=world.id,
                    display_name="duplicate-agent",
                    district_id=district.id,
                    business_type_id=business_type.id,
                    payout_lnaddress="different@example.com",
                )
            )
            raise AssertionError("duplicate display name was accepted")
        except ValueError as exc:
            assert str(exc) == "A claim for this display name is already pending."

    asyncio.run(_run())


def test_public_and_admin_reads_ignore_stale_pending_claims(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Read Only Pending Market")
        district, business_type = await default_claim_options(world.id)
        await update_district(district.copy(update={"slot_limit": 1}))

        stale_claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="stale-read",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="stale-read@example.com",
            )
        )
        stale_record = await get_payment_request(stale_claim.payment_request_id)
        assert stale_record is not None
        await update_payment_request(
            stale_record.copy(update={"created_at": pending_claim_cutoff() - timedelta(seconds=1)})
        )

        public_state = await build_public_world_state(world.id)
        public_district = next(item for item in public_state.districts if item.id == district.id)
        dashboard = await build_admin_dashboard(world.user_id)
        assert dashboard is not None
        admin_district = next(item for item in dashboard.districts if item.id == district.id)
        assert len(dashboard.pending_payments) == 0
        assert dashboard.summary["pending_payments"] == 0
        assert public_district.occupied_slots == 0
        assert public_district.pending_slots == 0
        assert public_district.available_slots == 1
        assert admin_district.pending_slots == 0
        assert admin_district.available_slots == 1

        stored = await get_payment_request(stale_claim.payment_request_id)
        assert stored is not None
        assert stored.status == "pending"

    asyncio.run(_run())


def test_expired_pending_claims_do_not_hold_slots(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Expired Pending Market")
        district, business_type = await default_claim_options(world.id)
        await update_district(district.copy(update={"slot_limit": 1}))

        stale_claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="stale",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="stale@example.com",
            )
        )
        stale_record = await get_payment_request(stale_claim.payment_request_id)
        assert stale_record is not None
        await update_payment_request(
            stale_record.copy(update={"created_at": pending_claim_cutoff() - timedelta(seconds=1)})
        )

        fresh_claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="fresh",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="fresh@example.com",
            )
        )

        stale_record = await get_payment_request(stale_claim.payment_request_id)
        assert stale_record is not None
        assert stale_record.status == "expired"
        assert fresh_claim.payment_request_id

    asyncio.run(_run())


def test_late_paid_expired_claim_still_settles_and_is_idempotent(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Late Paid Expired Market")
        district, business_type = await default_claim_options(world.id)

        claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="late-paid",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="late-paid@example.com",
            )
        )
        stored = await get_payment_request(claim.payment_request_id)
        assert stored is not None
        await update_payment_request(stored.copy(update={"created_at": pending_claim_cutoff() - timedelta(seconds=1)}))

        status = await get_claim_status(claim.payment_request_id)
        assert status.status == "expired"

        settled = await payment_received_for_claim(
            SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
        )
        settled_again = await payment_received_for_claim(
            SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
        )

        stored = await get_payment_request(claim.payment_request_id)
        assert settled is True
        assert settled_again is True
        assert stored is not None
        assert stored.status == "paid"
        assert stored.agent_id is not None
        assert stored.business_id is not None

    asyncio.run(_run())


def test_failed_settlement_resets_to_retryable_state(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Retryable Settlement Market")
        district, business_type = await default_claim_options(world.id)

        claim = await create_business_claim(
            ClaimBusinessRequest(
                world_id=world.id,
                display_name="retry-me",
                district_id=district.id,
                business_type_id=business_type.id,
                payout_lnaddress="retry-me@example.com",
            )
        )

        payment_update_calls = 0
        original_update_payment_request = update_payment_request

        async def flaky_update_payment_request(payment_request):
            nonlocal payment_update_calls
            if (
                payment_request.status == "paid"
                and payment_request.agent_id is not None
                and payment_request.business_id is not None
                and payment_update_calls == 0
            ):
                payment_update_calls += 1
                raise ValueError("final paid update failed")
            return await original_update_payment_request(payment_request)

        monkeypatch.setattr("market_town.services.update_payment_request", flaky_update_payment_request)

        settled = await payment_received_for_claim(
            SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
        )
        stored = await get_payment_request(claim.payment_request_id)
        agents = await list_agents(world.id)
        businesses = await list_businesses(world.id)
        assert settled is False
        assert stored is not None
        assert stored.status == "pending"
        assert stored.agent_id is not None
        assert stored.business_id is not None
        assert len(agents) == 1
        assert agents[0].id == stored.agent_id
        assert len(businesses) == 1
        assert businesses[0].id == stored.business_id

        settled_again = await payment_received_for_claim(
            SimpleNamespace(payment_hash=claim.payment_hash, extra={"tag": "market_town"})
        )
        stored = await get_payment_request(claim.payment_request_id)
        agents = await list_agents(world.id)
        businesses = await list_businesses(world.id)
        assert settled_again is True
        assert stored is not None
        assert stored.status == "paid"
        assert stored.agent_id == agents[0].id
        assert stored.business_id == businesses[0].id
        assert len(agents) == 1
        assert agents[0].id == stored.agent_id
        assert len(businesses) == 1
        assert businesses[0].id == stored.business_id

    asyncio.run(_run())


def test_paused_world_rejects_agent_runtime(monkeypatch):
    async def _run():
        patch_lightning(monkeypatch)
        world = await bootstrap_world(name="Paused Runtime Market")
        district, business_type = await default_claim_options(world.id)
        agent = await create_paid_agent(
            world,
            display_name="paused-agent",
            district_id=district.id,
            business_type_id=business_type.id,
        )
        await update_world(world.copy(update={"status": "paused"}))

        try:
            await get_agent_session(world.id, agent.api_key)
            raise AssertionError("paused world accepted an agent session")
        except ValueError as exc:
            assert str(exc) == "World is not active."

        try:
            await submit_strategy(world.id, agent, epoch_number=1)
            raise AssertionError("paused world accepted an agent action")
        except ValueError as exc:
            assert str(exc) == "World is not active."

    asyncio.run(_run())
