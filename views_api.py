from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, Header
from fastapi.exceptions import HTTPException
from lnbits.core.crud import get_wallet
from lnbits.core.models import SimpleStatus
from lnbits.core.models.users import AccountId
from lnbits.decorators import check_account_id_exists

from .crud import (
    delete_world,
    get_agent,
    get_business,
    get_business_type,
    get_district,
    get_world_by_id,
    get_world_for_user,
    list_businesses,
    list_districts,
)
from .models import (
    ActionPayload,
    AdminDashboard,
    AdminWorld,
    AgentCredentialReveal,
    AgentSession,
    Business,
    BusinessType,
    ClaimBusinessRequest,
    CreateWorld,
    District,
    Epoch,
    PaymentRequestResponse,
    PaymentStatusResponse,
    PublicWorldState,
    SafeAgent,
    SubmissionAccepted,
    UpdateBusinessType,
    UpdateDistrict,
    UpdateWorld,
    World,
)
from .realtime import get_admin_channel_id, get_public_world_channel_id
from .services import (
    build_admin_dashboard,
    build_public_world_state,
    create_business_claim,
    ensure_world_bootstrap,
    get_agent_session,
    get_claim_status,
    override_business_status,
    reset_world_seeds,
    resolve_epoch,
    reveal_claim_credentials,
    submit_action,
    to_safe_agent,
    update_agent_status,
    update_business_type_settings,
    update_district_settings,
    update_world_settings,
)

market_town_api_router = APIRouter()


async def require_owned_world(account_id: AccountId) -> World:
    world = await get_world_for_user(account_id.id)
    if not world:
        raise HTTPException(HTTPStatus.NOT_FOUND, "World not found.")
    return world


async def require_owned_wallet(wallet_id: str | None, account_id: AccountId) -> None:
    if not wallet_id:
        return
    wallet = await get_wallet(wallet_id)
    if not wallet or wallet.user != account_id.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Wallet not found for account.")


async def require_agent_session(
    world_id: str,
    x_api_key: str | None = Header(default=None),
) -> AgentSession:
    if not x_api_key:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Missing X-API-Key header.")
    try:
        return await get_agent_session(world_id, x_api_key)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, str(exc)) from exc


############################ Admin ############################
@market_town_api_router.post("/api/v1/world/bootstrap", response_model=AdminWorld, status_code=HTTPStatus.CREATED)
async def api_bootstrap_world(
    data: CreateWorld,
    account_id: AccountId = Depends(check_account_id_exists),
) -> World:
    await require_owned_wallet(data.wallet_id, account_id)
    await require_owned_wallet(data.fee_wallet_id, account_id)
    world = await ensure_world_bootstrap(account_id.id, data)
    return world


@market_town_api_router.get("/api/v1/world", response_model=AdminWorld)
async def api_get_world(
    account_id: AccountId = Depends(check_account_id_exists),
) -> World:
    return await require_owned_world(account_id)


@market_town_api_router.put("/api/v1/world", response_model=AdminWorld)
async def api_update_world(
    data: UpdateWorld,
    account_id: AccountId = Depends(check_account_id_exists),
) -> World:
    world = await require_owned_world(account_id)
    await require_owned_wallet(data.wallet_id, account_id)
    await require_owned_wallet(data.fee_wallet_id, account_id)
    return await update_world_settings(world, data)


@market_town_api_router.delete("/api/v1/world", response_model=SimpleStatus)
async def api_delete_world(
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    world = await require_owned_world(account_id)
    await delete_world(world.id)
    return SimpleStatus(success=True, message="World deleted")


@market_town_api_router.post("/api/v1/world/reset-seeds", response_model=SimpleStatus)
async def api_reset_world_seeds(
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    world = await require_owned_world(account_id)
    try:
        await reset_world_seeds(world)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    return SimpleStatus(success=True, message="World defaults reset")


@market_town_api_router.get(
    "/api/v1/admin/dashboard",
    response_model=AdminDashboard,
    response_model_exclude_none=True,
)
async def api_get_admin_dashboard(
    account_id: AccountId = Depends(check_account_id_exists),
) -> AdminDashboard:
    dashboard = await build_admin_dashboard(account_id.id)
    if not dashboard:
        raise HTTPException(HTTPStatus.NOT_FOUND, "World not found.")
    return dashboard


@market_town_api_router.get("/api/v1/admin/ws")
async def api_get_admin_ws_channel(
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    world = await require_owned_world(account_id)
    return {"channel": get_admin_channel_id(world.id)}


@market_town_api_router.get("/api/v1/districts", response_model=list[District])
async def api_list_districts(
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[District]:
    world = await require_owned_world(account_id)
    return await list_districts(world.id)


@market_town_api_router.put("/api/v1/districts/{district_id}", response_model=District)
async def api_update_district(
    district_id: str,
    data: UpdateDistrict,
    account_id: AccountId = Depends(check_account_id_exists),
) -> District:
    world = await require_owned_world(account_id)
    district = await get_district(district_id)
    if not district or district.world_id != world.id:
        raise HTTPException(HTTPStatus.NOT_FOUND, "District not found.")
    return await update_district_settings(district, data)


@market_town_api_router.get("/api/v1/business-types", response_model=list[BusinessType])
async def api_list_business_types(
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[BusinessType]:
    dashboard = await build_admin_dashboard(account_id.id)
    if not dashboard:
        raise HTTPException(HTTPStatus.NOT_FOUND, "World not found.")
    return dashboard.business_types


@market_town_api_router.put("/api/v1/business-types/{business_type_id}", response_model=BusinessType)
async def api_update_business_type(
    business_type_id: str,
    data: UpdateBusinessType,
    account_id: AccountId = Depends(check_account_id_exists),
) -> BusinessType:
    world = await require_owned_world(account_id)
    business_type = await get_business_type(business_type_id)
    if not business_type or business_type.world_id != world.id:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Business type not found.")
    return await update_business_type_settings(business_type, data)


@market_town_api_router.get("/api/v1/agents", response_model=list[SafeAgent])
async def api_list_agents(
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[SafeAgent]:
    dashboard = await build_admin_dashboard(account_id.id)
    if not dashboard:
        raise HTTPException(HTTPStatus.NOT_FOUND, "World not found.")
    return dashboard.agents


@market_town_api_router.put("/api/v1/agents/{agent_id}/status", response_model=SafeAgent)
async def api_update_agent_status(
    agent_id: str,
    status: Literal["active", "inactive"],
    account_id: AccountId = Depends(check_account_id_exists),
) -> SafeAgent:
    world = await require_owned_world(account_id)
    agent = await get_agent(agent_id)
    if not agent or agent.world_id != world.id:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Agent not found.")
    return to_safe_agent(await update_agent_status(agent, status))


@market_town_api_router.get("/api/v1/businesses", response_model=list[Business])
async def api_list_businesses(
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[Business]:
    world = await require_owned_world(account_id)
    return await list_businesses(world.id)


@market_town_api_router.put("/api/v1/businesses/{business_id}/status", response_model=Business)
async def api_update_business_status(
    business_id: str,
    status: Literal["active", "distress", "closed"],
    account_id: AccountId = Depends(check_account_id_exists),
) -> Business:
    world = await require_owned_world(account_id)
    business = await get_business(business_id)
    if not business or business.world_id != world.id:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Business not found.")
    return await override_business_status(business, status)


@market_town_api_router.get("/api/v1/epochs", response_model=list[Epoch])
async def api_list_epochs(
    account_id: AccountId = Depends(check_account_id_exists),
) -> list[Epoch]:
    dashboard = await build_admin_dashboard(account_id.id)
    if not dashboard:
        raise HTTPException(HTTPStatus.NOT_FOUND, "World not found.")
    return dashboard.epochs


@market_town_api_router.post("/api/v1/epochs/resolve", response_model=Epoch)
async def api_resolve_epoch(
    epoch_number: int | None = None,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Epoch:
    world = await require_owned_world(account_id)
    try:
        return await resolve_epoch(world.id, epoch_number)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


############################ Public ############################
@market_town_api_router.get("/api/v1/public/world/{world_id}", response_model=PublicWorldState)
async def api_get_public_world(world_id: str) -> PublicWorldState:
    try:
        return await build_public_world_state(world_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.NOT_FOUND, str(exc)) from exc


@market_town_api_router.get("/api/v1/public/world/{world_id}/ws")
async def api_get_public_ws_channel(world_id: str) -> dict:
    if not await get_world_by_id(world_id):
        raise HTTPException(HTTPStatus.NOT_FOUND, "World not found.")
    return {"channel": get_public_world_channel_id(world_id)}


@market_town_api_router.post(
    "/api/v1/public/world/{world_id}/claim",
    response_model=PaymentRequestResponse,
    status_code=HTTPStatus.CREATED,
)
async def api_create_claim(
    world_id: str,
    data: ClaimBusinessRequest,
) -> PaymentRequestResponse:
    payload = data.copy(update={"world_id": world_id})
    try:
        return await create_business_claim(payload)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Could not create claim invoice.") from exc


@market_town_api_router.get(
    "/api/v1/public/claims/{payment_request_id}",
    response_model=PaymentStatusResponse,
    response_model_exclude_none=True,
)
async def api_get_claim_status(payment_request_id: str) -> PaymentStatusResponse:
    try:
        return await get_claim_status(payment_request_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.NOT_FOUND, str(exc)) from exc


@market_town_api_router.post("/api/v1/public/claims/{claim_token}/reveal", response_model=AgentCredentialReveal)
async def api_reveal_claim_credentials(claim_token: str) -> AgentCredentialReveal:
    try:
        return await reveal_claim_credentials(claim_token)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


############################ Agent ############################
@market_town_api_router.get("/api/v1/agent/world/{world_id}/session", response_model=AgentSession)
async def api_get_agent_session(
    session: AgentSession = Depends(require_agent_session),
) -> AgentSession:
    return session


@market_town_api_router.post("/api/v1/agent/world/{world_id}/actions", response_model=SubmissionAccepted)
async def api_submit_action(
    payload: ActionPayload,
    world_id: str,
    x_api_key: str | None = Header(default=None),
) -> SubmissionAccepted:
    if not x_api_key:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Missing X-API-Key header.")
    try:
        return await submit_action(world_id, x_api_key, payload)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
