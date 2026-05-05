import json

from lnbits.core.services import websocket_updater

from .models import AdminEvent, PublicWorldEvent


def get_admin_channel_id(world_id: str) -> str:
    return f"market-town-admin-{world_id}"


def get_public_world_channel_id(world_id: str) -> str:
    return f"market-town-public-{world_id}"


async def publish_admin_event(
    world_id: str,
    *,
    scope: str,
    event: str,
    entity_id: str | None = None,
) -> None:
    payload = AdminEvent(
        scope=scope,
        event=event,
        entity_id=entity_id,
        world_id=world_id,
    )
    await websocket_updater(get_admin_channel_id(world_id), json.dumps(payload.dict()))


async def publish_public_event(
    world_id: str,
    *,
    event: str,
    epoch_number: int | None = None,
    payment_request_id: str | None = None,
    payment_hash: str | None = None,
) -> None:
    payload = PublicWorldEvent(
        world_id=world_id,
        event=event,
        epoch_number=epoch_number,
        payment_request_id=payment_request_id,
        payment_hash=payment_hash,
    )
    await websocket_updater(get_public_world_channel_id(world_id), json.dumps(payload.dict()))


async def publish_payment_event(payment_hash: str, payload: dict) -> None:
    await websocket_updater(payment_hash, json.dumps(payload))
