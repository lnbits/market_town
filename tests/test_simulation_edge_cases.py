import asyncio
from types import SimpleNamespace

from market_town.crud import (  # type: ignore[import]
    get_payment_request,
    list_business_types,
    update_district,
)
from market_town.models import ActionPayload, ClaimBusinessRequest
from market_town.services import (  # type: ignore[import]
    build_public_world_state,
    create_business_claim,
    payment_received_for_claim,
    submit_action,
)

from .simulation_helpers import (
    bootstrap_world,
    create_paid_agent,
    current_session,
    default_claim_options,
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
