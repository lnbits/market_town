import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from lnbits.core.models.users import AccountId

from market_town import market_town_ext  # type: ignore[import]
from market_town.crud import get_world_by_id  # type: ignore[import]
from market_town.services import payment_received_for_claim  # type: ignore[import]
from market_town.views_api import check_account_id_exists  # type: ignore[import]


def _wallet(wallet_id: str, user_id: str):
    return SimpleNamespace(id=wallet_id, user=user_id)


async def _client(
    monkeypatch, user_id: str, wallet_owner: str | None = None
) -> AsyncClient:
    app = FastAPI()
    app.include_router(market_town_ext)

    async def fake_account():
        return AccountId(id=user_id)

    async def fake_get_wallet(wallet_id: str):
        return _wallet(wallet_id, wallet_owner or user_id)

    app.dependency_overrides[check_account_id_exists] = fake_account
    monkeypatch.setattr("market_town.views_api.get_wallet", fake_get_wallet)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    return AsyncClient(transport=transport, base_url="http://testserver")


def _patch_payment_services(monkeypatch, payment_hash: str = "hash-api-claim"):
    async def fake_create_invoice(*args, **kwargs):
        if kwargs["wallet_id"].endswith("-fees"):
            return SimpleNamespace(payment_hash=f"{payment_hash}-fee", bolt11="lnbc1fee")
        return SimpleNamespace(payment_hash=payment_hash, bolt11="lnbc1claim")

    async def fake_pay_invoice(**kwargs):
        return SimpleNamespace(ok=True)

    async def fake_pay_tribute(*args, **kwargs):
        return None

    monkeypatch.setattr("market_town.services.create_invoice", fake_create_invoice)
    monkeypatch.setattr("market_town.services.pay_invoice", fake_pay_invoice)
    monkeypatch.setattr("market_town.services.pay_tribute", fake_pay_tribute)


def test_api_all_endpoints_and_private_fields(monkeypatch):
    async def _run():
        user_id = uuid4().hex
        wallet_id = f"{user_id}-wallet"
        fee_wallet_id = f"{user_id}-fees"
        _patch_payment_services(monkeypatch)
        client = await _client(monkeypatch, user_id)
        try:
            bootstrap = await client.post(
                "/market_town/api/v1/world/bootstrap",
                json={
                    "name": "API Market",
                    "wallet_id": wallet_id,
                    "fee_wallet_id": fee_wallet_id,
                },
            )
            assert bootstrap.status_code == 201
            world = bootstrap.json()
            assert "user_id" not in world
            assert "world_seed" not in world
            assert world["wallet_id"] == wallet_id

            world_id = world["id"]
            get_world = await client.get("/market_town/api/v1/world")
            assert get_world.status_code == 200
            assert "user_id" not in get_world.json()

            updated_world = await client.put(
                "/market_town/api/v1/world",
                json={"name": "API Market Updated", "status": "paused"},
            )
            assert updated_world.status_code == 200
            assert updated_world.json()["status"] == "paused"

            await client.put("/market_town/api/v1/world", json={"status": "active"})

            dashboard = await client.get("/market_town/api/v1/admin/dashboard")
            assert dashboard.status_code == 200
            assert "user_id" not in dashboard.json()["world"]

            admin_ws = await client.get("/market_town/api/v1/admin/ws")
            assert admin_ws.status_code == 200
            assert user_id not in admin_ws.json()["channel"]
            assert world_id in admin_ws.json()["channel"]

            districts = await client.get("/market_town/api/v1/districts")
            assert districts.status_code == 200
            district = districts.json()[0]

            update_district = await client.put(
                f"/market_town/api/v1/districts/{district['id']}",
                json={"name": "Central API", "slot_limit": 2},
            )
            assert update_district.status_code == 200
            assert update_district.json()["name"] == "Central API"

            business_types = await client.get("/market_town/api/v1/business-types")
            assert business_types.status_code == 200
            business_type = business_types.json()[0]

            update_business_type = await client.put(
                f"/market_town/api/v1/business-types/{business_type['id']}",
                json={"name": "API Cart", "open_fee_sat": 500},
            )
            assert update_business_type.status_code == 200
            assert update_business_type.json()["name"] == "API Cart"

            public_world = await client.get(
                f"/market_town/api/v1/public/world/{world_id}"
            )
            assert public_world.status_code == 200
            public_payload = public_world.json()
            assert "user_id" not in public_payload["world"]
            assert "config_text" not in public_payload["districts"][0]
            assert "config_text" not in public_payload["business_types"][0]

            public_ws = await client.get(
                f"/market_town/api/v1/public/world/{world_id}/ws"
            )
            assert public_ws.status_code == 200
            assert public_ws.json()["channel"] == f"market-town-public-{world_id}"

            claim = await client.post(
                f"/market_town/api/v1/public/world/{world_id}/claim",
                json={
                    "display_name": "api-agent",
                    "district_id": district["id"],
                    "business_type_id": business_type["id"],
                    "payout_lnaddress": "api@example.com",
                },
            )
            assert claim.status_code == 201
            claim_payload = claim.json()
            assert claim_payload["claim_token"]

            status = await client.get(
                f"/market_town/api/v1/public/claims/{claim_payload['payment_request_id']}"
            )
            assert status.status_code == 200
            assert "claim_token" not in status.json()

            settled = await payment_received_for_claim(
                SimpleNamespace(
                    payment_hash=claim_payload["payment_hash"],
                    extra={"tag": "market_town"},
                )
            )
            assert settled is True

            reveal = await client.post(
                f"/market_town/api/v1/public/claims/{claim_payload['claim_token']}/reveal"
            )
            assert reveal.status_code == 200
            credentials = reveal.json()
            assert credentials["api_key"]

            agents = await client.get("/market_town/api/v1/agents")
            assert agents.status_code == 200
            assert agents.json()
            assert "api_key_hash" not in agents.json()[0]

            agent_status = await client.put(
                f"/market_town/api/v1/agents/{credentials['agent_id']}/status?status=inactive"
            )
            assert agent_status.status_code == 200
            assert "api_key_hash" not in agent_status.json()

            await client.put(
                f"/market_town/api/v1/agents/{credentials['agent_id']}/status?status=active"
            )

            businesses = await client.get("/market_town/api/v1/businesses")
            assert businesses.status_code == 200
            assert businesses.json()

            business_status = await client.put(
                f"/market_town/api/v1/businesses/{credentials['business_id']}/status?status=distress"
            )
            assert business_status.status_code == 200
            assert business_status.json()["status"] == "distress"

            await client.put(
                f"/market_town/api/v1/businesses/{credentials['business_id']}/status?status=active"
            )

            epochs = await client.get("/market_town/api/v1/epochs")
            assert epochs.status_code == 200
            assert epochs.json()

            session = await client.get(
                f"/market_town/api/v1/agent/world/{world_id}/session",
                headers={"X-API-Key": credentials["api_key"]},
            )
            assert session.status_code == 200
            session_payload = session.json()
            assert "api_key_hash" not in session_payload["agent"]

            action = await client.post(
                f"/market_town/api/v1/agent/world/{world_id}/actions",
                headers={"X-API-Key": credentials["api_key"]},
                json={
                    "epoch": session_payload["current_epoch"]["epoch_number"],
                    "business_id": credentials["business_id"],
                    "price_sat": 220,
                    "restock_units": 10,
                    "maintenance_budget_sat": 5,
                    "quality_budget_sat": 5,
                },
            )
            assert action.status_code == 200
            assert action.json()["accepted"] is True

            resolved = await client.post(
                "/market_town/api/v1/epochs/resolve"
                f"?epoch_number={session_payload['current_epoch']['epoch_number']}"
            )
            assert resolved.status_code == 200
            assert resolved.json()["status"] == "resolved"

            reset = await client.post("/market_town/api/v1/world/reset-seeds")
            assert reset.status_code == 200
            assert reset.json()["success"] is True

            delete = await client.delete("/market_town/api/v1/world")
            assert delete.status_code == 200
            assert delete.json()["success"] is True
            assert await get_world_by_id(world_id) is None
            deleted_world = await client.get("/market_town/api/v1/world")
            assert deleted_world.status_code == 404
            deleted_public_world = await client.get(
                f"/market_town/api/v1/public/world/{world_id}"
            )
            assert deleted_public_world.status_code == 404
        finally:
            await client.aclose()

    asyncio.run(_run())


def test_world_wallet_must_belong_to_user(monkeypatch):
    async def _run():
        user_id = uuid4().hex
        client = await _client(monkeypatch, user_id, wallet_owner="other-user")
        try:
            response = await client.post(
                "/market_town/api/v1/world/bootstrap",
                json={"name": "Wrong Wallet", "wallet_id": "foreign-wallet"},
            )
            assert response.status_code == 403
        finally:
            await client.aclose()

    asyncio.run(_run())
