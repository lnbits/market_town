import asyncio
import json
import math
from datetime import datetime, timedelta
from math import floor
from random import Random
from secrets import token_urlsafe

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, get_pr_from_lnurl, pay_invoice
from loguru import logger

from .crud import (
    create_agent,
    create_audit_event,
    create_business,
    create_business_type,
    create_district,
    create_epoch,
    create_payment_request,
    create_season_result,
    create_snapshot,
    create_submission,
    create_world,
    generate_api_key,
    get_active_business_count_for_district,
    get_active_business_for_agent,
    get_agent,
    get_business_type,
    get_business_type_by_key,
    get_district,
    get_district_by_key,
    get_effective_submission_for_epoch,
    get_epoch,
    get_latest_submission_for_business,
    get_payment_request,
    get_payment_request_by_claim_token,
    get_payment_request_by_hash,
    get_world_by_id,
    get_world_for_user,
    hash_api_key,
    list_agents,
    list_business_types,
    list_businesses,
    list_districts,
    list_epochs,
    list_paid_payment_requests_for_season,
    list_pending_payment_requests,
    list_season_results,
    list_snapshots_for_business,
    list_submissions,
    list_unresolved_epochs_before,
    update_agent,
    update_business,
    update_business_type,
    update_district,
    update_epoch,
    update_payment_request,
    update_season_result,
    update_world,
)
from .models import (
    ActionPayload,
    AdminDashboard,
    AdminWorld,
    Agent,
    AgentCredentialReveal,
    AgentSession,
    Business,
    BusinessBoardItem,
    BusinessEpochSnapshot,
    BusinessType,
    CreateBusinessType,
    CreateDistrict,
    CreateWorld,
    District,
    Epoch,
    EpochDigest,
    LeaderboardEntry,
    PaymentRequestRecord,
    PaymentRequestResponse,
    PaymentStatusResponse,
    PublicBusinessType,
    PublicDistrict,
    PublicWorld,
    PublicWorldState,
    SafeAgent,
    SeasonResult,
    SubmissionAccepted,
    UpdateBusinessType,
    UpdateDistrict,
    UpdateWorld,
    World,
    utc_now,
)
from .realtime import publish_admin_event, publish_payment_event, publish_public_event

runtime_locks: dict[str, asyncio.Lock] = {}
settlement_locks: dict[str, asyncio.Lock] = {}
reveal_locks: dict[str, asyncio.Lock] = {}
LNBITS_TRIBUTE_PERCENT = 2.0
LNBITS_TRIBUTE_ADDRESS = "lnbits@nostr.com"

DEFAULT_DISTRICTS: list[CreateDistrict] = [
    CreateDistrict(
        district_key="central_square",
        name="Central Square",
        footfall_base=160,
        affluence=1.2,
        price_sensitivity=0.9,
        quality_preference=1.1,
        slot_limit=8,
    ),
    CreateDistrict(
        district_key="train_station",
        name="Train Station",
        footfall_base=210,
        affluence=0.9,
        price_sensitivity=1.2,
        quality_preference=0.8,
        slot_limit=10,
    ),
    CreateDistrict(
        district_key="school_zone",
        name="School Zone",
        footfall_base=140,
        affluence=0.8,
        price_sensitivity=1.3,
        quality_preference=0.8,
        slot_limit=8,
    ),
    CreateDistrict(
        district_key="office_park",
        name="Office Park",
        footfall_base=170,
        affluence=1.1,
        price_sensitivity=0.95,
        quality_preference=1.0,
        slot_limit=8,
    ),
    CreateDistrict(
        district_key="residential_block",
        name="Residential Block",
        footfall_base=120,
        affluence=0.95,
        price_sensitivity=1.05,
        quality_preference=0.95,
        slot_limit=8,
    ),
    CreateDistrict(
        district_key="night_market",
        name="Night Market",
        footfall_base=190,
        affluence=1.0,
        price_sensitivity=1.1,
        quality_preference=1.05,
        slot_limit=12,
    ),
]

DEFAULT_BUSINESS_TYPES: list[CreateBusinessType] = [
    CreateBusinessType(
        type_key="coffee_cart",
        name="Coffee Cart",
        category="beverages",
        open_fee_sat=500,
        base_unit_cost_sat=120,
        fixed_rent_sat=14,
        base_capacity_units=38,
    ),
    CreateBusinessType(
        type_key="snack_stall",
        name="Snack Stall",
        category="food",
        open_fee_sat=500,
        base_unit_cost_sat=100,
        fixed_rent_sat=12,
        base_capacity_units=42,
    ),
    CreateBusinessType(
        type_key="fruit_stand",
        name="Fruit Stand",
        category="produce",
        open_fee_sat=450,
        base_unit_cost_sat=80,
        fixed_rent_sat=10,
        base_capacity_units=48,
    ),
    CreateBusinessType(
        type_key="vending_machine",
        name="Vending Machine",
        category="automated",
        open_fee_sat=650,
        base_unit_cost_sat=90,
        fixed_rent_sat=18,
        base_capacity_units=55,
    ),
]

EVENT_CATALOG = [
    ("festival_day", "Festival Day", 1.25),
    ("commuter_rush", "Commuter Rush", 1.15),
    ("tourist_wave", "Tourist Wave", 1.2),
]

SEASON_PAYOUT_WEIGHTS = [60, 30, 10]


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def epoch_seconds(world: World) -> int:
    return world.epoch_duration_hours * 3600


def current_utc_epoch_number(world: World, now: datetime | None = None) -> int:
    now = now or utc_now()
    started_at = world.started_at or now
    elapsed_seconds = max(0, int((now - started_at).total_seconds()))
    return (elapsed_seconds // epoch_seconds(world)) + 1


def epoch_window(world: World, epoch_number: int) -> tuple[datetime, datetime, datetime]:
    epoch_offset = max(0, epoch_number - 1)
    started_at = world.started_at + timedelta(seconds=epoch_offset * epoch_seconds(world))
    digest_at = started_at + timedelta(seconds=epoch_seconds(world))
    submission_deadline_at = digest_at - timedelta(minutes=world.submission_cutoff_minutes)
    return started_at, submission_deadline_at, digest_at


def world_started_at_for_epoch(world: World, epoch_number: int, now: datetime) -> datetime:
    epoch_offset = max(0, epoch_number - 1)
    return now - timedelta(seconds=epoch_offset * epoch_seconds(world))


def season_number_for_epoch(world: World, epoch_number: int) -> int:
    if epoch_number <= 0:
        return 0
    return ((epoch_number - 1) // world.season_length_epochs) + 1


async def world_has_active_businesses(world_id: str) -> bool:
    businesses = await list_businesses(world_id)
    return any(item.status != "closed" for item in businesses)


def fee_breakdown(amount_sat: int, operator_fee_percent: float) -> tuple[int, int]:
    base_amount = max(0, amount_sat)
    operations = floor(base_amount * max(0.0, operator_fee_percent) / 100.0)
    return operations, max(0, base_amount - operations - calculate_tribute_amount(base_amount))


def calculate_tribute_amount(amount_sat: int) -> int:
    return floor(max(0, amount_sat) * LNBITS_TRIBUTE_PERCENT / 100.0)


def to_admin_world(world: World) -> AdminWorld:
    return AdminWorld.parse_obj(world.dict(exclude={"user_id", "world_seed"}))


def to_safe_agent(agent: Agent) -> SafeAgent:
    return SafeAgent.parse_obj(agent.dict(exclude={"api_key_hash"}))


async def to_public_district(district: District) -> PublicDistrict:
    occupied_slots = await get_active_business_count_for_district(district.world_id, district.id)
    pending_slots = len(
        [
            item
            for item in await list_pending_payment_requests(district.world_id)
            if item.district_id == district.id
        ]
    )
    return PublicDistrict.parse_obj(
        {
            **district.dict(exclude={"config_text", "created_at", "updated_at"}),
            "occupied_slots": occupied_slots,
            "pending_slots": pending_slots,
            "available_slots": max(0, district.slot_limit - occupied_slots - pending_slots),
        }
    )


def to_public_business_type(business_type: BusinessType) -> PublicBusinessType:
    return PublicBusinessType.parse_obj(
        business_type.dict(exclude={"config_text", "created_at", "updated_at"})
    )


def validate_lnaddress(value: str) -> None:
    if value.count("@") != 1:
        raise ValueError("Payout LN address must be a valid Lightning address.")
    name, domain = value.split("@", 1)
    if not name or not domain or "." not in domain:
        raise ValueError("Payout LN address must be a valid Lightning address.")


def calculate_season_payout_amounts(
    prize_pool_sat: int, leaderboard: list[LeaderboardEntry]
) -> dict[str, int]:
    if prize_pool_sat <= 0 or not leaderboard:
        return {}
    winners = [entry for entry in leaderboard[: len(SEASON_PAYOUT_WEIGHTS)] if entry.business_id]
    if not winners:
        return {}
    payouts: dict[str, int] = {}
    allocated = 0
    for index, entry in enumerate(winners):
        amount = floor(prize_pool_sat * SEASON_PAYOUT_WEIGHTS[index] / 100)
        if amount <= 0:
            continue
        payouts[entry.business_id] = amount
        allocated += amount
    remainder = prize_pool_sat - allocated
    if remainder > 0:
        winner = winners[0]
        payouts[winner.business_id] = payouts.get(winner.business_id, 0) + remainder
    return payouts


async def pay_tribute(tribute: int, wallet_id: str) -> None:
    if tribute <= 0:
        return
    pr = await get_pr_from_lnurl(
        LNBITS_TRIBUTE_ADDRESS,
        tribute * 1000,
        comment="Market Town tribute",
    )
    await pay_invoice(
        wallet_id=wallet_id,
        payment_request=pr,
        max_sat=tribute,
        description="Tribute to help support LNbits",
    )


async def settle_operator_fee(
    fee_amount_sat: int, world_wallet_id: str, fee_wallet_id: str | None, world_id: str
) -> None:
    if fee_amount_sat <= 0 or not fee_wallet_id or fee_wallet_id == world_wallet_id:
        return
    operator_invoice = await create_invoice(
        wallet_id=fee_wallet_id,
        amount=fee_amount_sat,
        memo=f"Market Town operator fee for world {world_id}",
        extra={"tag": "market_town_operator_fee", "world_id": world_id},
    )
    await pay_invoice(
        wallet_id=world_wallet_id,
        payment_request=operator_invoice.bolt11,
        max_sat=fee_amount_sat,
        description=f"Market Town operator fee for world {world_id}",
        tag="market_town_operator_fee",
    )


async def settle_season_payouts(
    world: World,
    season_result: SeasonResult,
    leaderboard: list[LeaderboardEntry],
) -> SeasonResult:
    season_started_at, _, _ = epoch_window(world, season_result.epoch_start)
    _, _, season_ended_at = epoch_window(world, season_result.epoch_end)
    paid_requests = await list_paid_payment_requests_for_season(
        world.id,
        season_started_at,
        season_ended_at,
        include_before_start=season_result.season_number == 1,
    )
    prize_pool_sat = sum(item.prize_pool_amount_sat for item in paid_requests)
    payout_amounts = calculate_season_payout_amounts(prize_pool_sat, leaderboard)
    businesses = {business.id: business for business in await list_businesses(world.id)}
    agents = {agent.id: agent for agent in await list_agents(world.id)}
    payouts = []

    for business_id, amount_sat in payout_amounts.items():
        business = businesses.get(business_id)
        agent = agents.get(business.agent_id) if business else None
        payout = {
            "business_id": business_id,
            "agent_id": agent.id if agent else None,
            "amount_sat": amount_sat,
            "status": "pending",
            "payment_hash": None,
        }
        if not agent or not agent.payout_lnaddress:
            payout["status"] = "failed"
            payout["error"] = "Missing payout Lightning address."
            payouts.append(payout)
            continue
        try:
            payment_request = await get_pr_from_lnurl(
                agent.payout_lnaddress,
                amount_sat * 1000,
                comment=f"Market Town season {season_result.season_number} payout",
            )
            payment = await pay_invoice(
                wallet_id=world.wallet_id,
                payment_request=payment_request,
                max_sat=amount_sat,
                extra={
                    "tag": "market_town_season_payout",
                    "world_id": world.id,
                    "season_number": season_result.season_number,
                    "business_id": business_id,
                    "agent_id": agent.id,
                },
                description=f"Market Town season {season_result.season_number} payout",
                tag="market_town_season_payout",
            )
            payout["status"] = "paid"
            payout["payment_hash"] = payment.payment_hash
        except Exception as exc:
            payout["status"] = "failed"
            payout["error"] = str(exc)
        payouts.append(payout)

    paid_count = len([item for item in payouts if item["status"] == "paid"])
    if not payouts:
        payout_status = "none"
    elif paid_count == len(payouts):
        payout_status = "paid"
    elif paid_count > 0:
        payout_status = "partial"
    else:
        payout_status = "failed"

    summary = {
        "scheme": "top_3_60_30_10",
        "prize_pool_sat": prize_pool_sat,
        "payment_request_ids": [item.id for item in paid_requests],
        "payouts": payouts,
    }
    return await update_season_result(
        season_result.copy(
            update={
                "payout_status": payout_status,
                "payout_summary_text": json.dumps(summary),
            }
        )
    )


async def seed_defaults(world_id: str, replace: bool = False) -> None:
    if replace:
        from .crud import delete_business_types_for_world, delete_districts_for_world

        await delete_districts_for_world(world_id)
        await delete_business_types_for_world(world_id)

    for district in DEFAULT_DISTRICTS:
        existing_district = await get_district_by_key(world_id, district.district_key)
        if existing_district:
            continue
        await create_district(world_id, district)

    for business_type in DEFAULT_BUSINESS_TYPES:
        existing_business_type = await get_business_type_by_key(world_id, business_type.type_key)
        if existing_business_type:
            continue
        await create_business_type(world_id, business_type)


async def ensure_world_bootstrap(user_id: str, data: CreateWorld) -> World:
    existing = await get_world_for_user(user_id)
    if existing:
        return existing

    world = await create_world(user_id, data)
    world = await update_world(
        world.copy(
            update={
                "current_epoch_number": 0,
                "current_season_number": 0,
            }
        )
    )
    await seed_defaults(world.id)
    await create_audit_event(world.id, "world_bootstrapped", world.id)
    return world


async def update_world_settings(world: World, data: UpdateWorld) -> World:
    updated = await update_world(world.copy(update=data.dict(exclude_unset=True)))
    await ensure_current_epoch(updated)
    await create_audit_event(updated.id, "world_updated", updated.id, payload=data.dict(exclude_unset=True))
    return updated


async def ensure_current_epoch(world: World) -> Epoch | None:
    if not await world_has_active_businesses(world.id):
        season_number = season_number_for_epoch(world, max(1, world.current_epoch_number))
        if world.current_season_number != season_number or world.active_event_id:
            await update_world(
                world.copy(
                    update={
                        "current_season_number": season_number,
                        "active_event_id": None,
                        "active_event_name": None,
                        "active_event_multiplier": 1.0,
                        "active_event_remaining_epochs": 0,
                    }
                )
            )
        return None

    current_epoch_number = current_utc_epoch_number(world)
    season_number = season_number_for_epoch(world, current_epoch_number)
    epoch = await get_epoch(world.id, current_epoch_number)
    if epoch:
        if world.current_epoch_number != current_epoch_number or world.current_season_number != season_number:
            await update_world(
                world.copy(
                    update={
                        "current_epoch_number": current_epoch_number,
                        "current_season_number": season_number,
                    }
                )
            )
        return epoch

    started_at, submission_deadline_at, digest_at = epoch_window(world, current_epoch_number)
    epoch = Epoch(
        id=token_urlsafe(12),
        world_id=world.id,
        epoch_number=current_epoch_number,
        season_number=season_number,
        started_at=started_at,
        submission_deadline_at=submission_deadline_at,
        digest_at=digest_at,
        status="open",
    )
    await create_epoch(epoch)
    await update_world(
        world.copy(
            update={
                "current_epoch_number": current_epoch_number,
                "current_season_number": season_number,
            }
        )
    )
    return epoch


async def retire_season_businesses(world: World, season_result: SeasonResult) -> None:
    businesses = [item for item in await list_businesses(world.id) if item.status != "closed"]
    agent_ids = {item.agent_id for item in businesses}
    now = utc_now()
    for business in businesses:
        await update_business(
            business.copy(
                update={
                    "status": "closed",
                    "closed_at": now,
                }
            )
        )
    agents = {agent.id: agent for agent in await list_agents(world.id)}
    for agent_id in agent_ids:
        agent = agents.get(agent_id)
        if agent:
            await update_agent(agent.copy(update={"status": "inactive"}))
    await create_audit_event(
        world.id,
        "season_businesses_retired",
        season_result.id,
        payload={
            "season_number": season_result.season_number,
            "business_count": len(businesses),
            "agent_count": len(agent_ids),
        },
    )


async def ensure_runtime_world_state(world: World) -> World:
    refreshed = await get_world_by_id(world.id)
    if not refreshed:
        raise ValueError("World not found.")
    await ensure_current_epoch(refreshed)
    refreshed = await maybe_progress_world_events(refreshed)
    return refreshed


async def maybe_progress_world_events(world: World) -> World:
    if world.current_epoch_number <= 0:
        return world
    if world.active_event_remaining_epochs > 0:
        return world
    rng = Random(f"{world.world_seed}:{world.current_epoch_number}")
    if rng.random() >= 0.03:
        return world
    event_id, event_name, multiplier = EVENT_CATALOG[rng.randrange(len(EVENT_CATALOG))]
    duration = rng.randint(1, 3)
    updated = world.copy(
        update={
            "active_event_id": event_id,
            "active_event_name": event_name,
            "active_event_multiplier": multiplier,
            "active_event_remaining_epochs": duration,
        }
    )
    return await update_world(updated)


async def build_admin_dashboard(user_id: str) -> AdminDashboard | None:
    world = await get_world_for_user(user_id)
    if not world:
        return None
    world = await ensure_runtime_world_state(world)
    current_epoch = await ensure_current_epoch(world)
    districts = [await to_public_district(item) for item in await list_districts(world.id)]
    business_types = await list_business_types(world.id)
    agents = await list_agents(world.id)
    raw_businesses = await list_businesses(world.id)
    businesses = await build_business_board(world)
    epochs = await list_epochs(world.id, limit=20)
    submissions = await list_submissions(world.id, limit=50)
    season_results = await list_season_results(world.id)
    pending_payments = [
        PaymentStatusResponse(
            payment_request_id=item.id,
            payment_hash=item.payment_hash,
            status=item.status,
            paid_at=item.paid_at,
        )
        for item in await list_pending_payment_requests(world.id)
    ]
    summary = {
        "active_businesses": len([b for b in raw_businesses if b.status != "closed"]),
        "pending_payments": len(pending_payments),
        "current_season": world.current_season_number,
        "current_epoch": current_epoch.epoch_number if current_epoch else None,
    }
    return AdminDashboard(
        world=to_admin_world(world),
        current_epoch=current_epoch,
        districts=districts,
        business_types=business_types,
        agents=[to_safe_agent(agent) for agent in agents],
        businesses=businesses,
        epochs=epochs,
        submissions=submissions,
        season_results=season_results,
        pending_payments=pending_payments,
        summary=summary,
    )


async def build_business_board(world: World) -> list[BusinessBoardItem]:
    districts = {district.id: district for district in await list_districts(world.id)}
    business_types = {item.id: item for item in await list_business_types(world.id)}
    items: list[BusinessBoardItem] = []
    for business in await list_businesses(world.id):
        district = districts.get(business.district_id)
        business_type = business_types.get(business.business_type_id)
        latest_snapshots = await list_snapshots_for_business(business.id, limit=1)
        latest_snapshot = latest_snapshots[0] if latest_snapshots else None
        cash_delta_sat = (
            latest_snapshot.cash_after - latest_snapshot.cash_before if latest_snapshot else 0
        )
        cash_delta_percent = None
        if latest_snapshot and latest_snapshot.cash_before != 0:
            cash_delta_percent = (cash_delta_sat / abs(latest_snapshot.cash_before)) * 100
        items.append(
            BusinessBoardItem(
                business_id=business.id,
                agent_id=business.agent_id,
                display_name=business.display_name,
                district_id=business.district_id,
                district_name=district.name if district else business.district_id,
                business_type_name=business_type.name if business_type else business.business_type_id,
                status=business.status,
                cash_sat=business.cash_sat,
                reputation=business.reputation,
                reliability=business.reliability,
                quality_level=business.quality_level,
                price_sat=business.price_sat,
                stock_units=business.stock_units,
                latest_profit_sat=latest_snapshot.profit_sat if latest_snapshot else 0,
                latest_revenue_sat=latest_snapshot.revenue_sat if latest_snapshot else 0,
                latest_units_sold=latest_snapshot.units_sold if latest_snapshot else 0,
                cash_delta_sat=cash_delta_sat,
                cash_delta_percent=cash_delta_percent,
                latest_snapshot_epoch=latest_snapshot.epoch_number if latest_snapshot else None,
            )
        )
    items.sort(key=lambda item: (item.status != "active", -item.cash_sat, -item.reputation))
    return items


def build_leaderboard(items: list[BusinessBoardItem]) -> list[LeaderboardEntry]:
    leaderboard: list[LeaderboardEntry] = []
    for item in items[:10]:
        leaderboard.append(
            LeaderboardEntry(
                business_id=item.business_id,
                agent_id=getattr(item, "agent_id", ""),
                business_name=item.display_name,
                district_name=item.district_name,
                cash_sat=item.cash_sat,
                cash_delta_sat=item.cash_delta_sat,
                cash_delta_percent=item.cash_delta_percent,
                latest_profit_sat=item.latest_profit_sat,
                latest_revenue_sat=item.latest_revenue_sat,
                latest_units_sold=item.latest_units_sold,
                price_sat=item.price_sat,
                stock_units=item.stock_units,
                reputation=item.reputation,
                reliability=item.reliability,
                quality_level=item.quality_level,
            )
        )
    return leaderboard


async def build_public_world_state(world_id: str) -> PublicWorldState:
    world = await get_world_by_id(world_id)
    if not world:
        raise ValueError("World not found.")
    world = await ensure_runtime_world_state(world)
    current_epoch = await ensure_current_epoch(world)
    board = await build_business_board(world)
    epochs = await list_epochs(world.id, limit=5)
    recent_digests = [
        EpochDigest(
            world_id=world.id,
            epoch_number=epoch.epoch_number,
            season_number=epoch.season_number,
            active_event_name=world.active_event_name,
            resolved_business_count=len(board),
            top_businesses=build_leaderboard(board)[:3],
            summary=epoch.digest_text or epoch.event_summary_text or "",
        )
        for epoch in epochs
    ]
    return PublicWorldState(
        world=PublicWorld(
            id=world.id,
            name=world.name,
            status=world.status,
            current_epoch_number=world.current_epoch_number,
            current_season_number=world.current_season_number,
            epoch_duration_hours=world.epoch_duration_hours,
            submission_cutoff_minutes=world.submission_cutoff_minutes,
            season_length_epochs=world.season_length_epochs,
            active_event_name=world.active_event_name,
            active_event_multiplier=world.active_event_multiplier,
            active_event_remaining_epochs=world.active_event_remaining_epochs,
            last_digest_text=world.last_digest_text,
            started_at=world.started_at,
            updated_at=world.updated_at,
        ),
        current_epoch=current_epoch,
        districts=[await to_public_district(item) for item in await list_districts(world.id)],
        business_types=[
            to_public_business_type(item) for item in await list_business_types(world.id)
        ],
        businesses=board,
        leaderboard=build_leaderboard(board),
        recent_digests=recent_digests,
    )


async def create_business_claim(data) -> PaymentRequestResponse:
    world = await get_world_by_id(data.world_id)
    if not world:
        raise ValueError("World not found.")
    if world.status != "active":
        raise ValueError("World is not active.")
    district = await get_district(data.district_id)
    business_type = await get_business_type(data.business_type_id)
    if not district or district.world_id != world.id:
        raise ValueError("District not found.")
    if not business_type or business_type.world_id != world.id:
        raise ValueError("Business type not found.")
    validate_lnaddress(data.payout_lnaddress)
    used_slots = await get_active_business_count_for_district(world.id, district.id)
    pending_slots = len(
        [
            item
            for item in await list_pending_payment_requests(world.id)
            if item.district_id == district.id
        ]
    )
    if used_slots + pending_slots >= district.slot_limit:
        raise ValueError("District is full.")

    amount_sat = business_type.open_fee_sat
    operations_amount_sat, prize_pool_amount_sat = fee_breakdown(
        amount_sat, world.operator_fee_percent
    )
    lnbits_tribute_amount_sat = calculate_tribute_amount(amount_sat)
    claim_token = token_urlsafe(24)
    payment = await create_invoice(
        wallet_id=world.wallet_id,
        amount=amount_sat,
        memo=f"Market Town opening fee for {data.display_name}",
        extra={
            "tag": "market_town",
            "world_id": world.id,
            "district_id": district.id,
            "business_type_id": business_type.id,
            "display_name": data.display_name,
            "payout_lnaddress": data.payout_lnaddress,
        },
    )
    record = PaymentRequestRecord(
        id=token_urlsafe(12),
        world_id=world.id,
        district_id=district.id,
        business_type_id=business_type.id,
        display_name=data.display_name,
        payout_lnaddress=data.payout_lnaddress,
        payment_hash=payment.payment_hash,
        payment_request=payment.bolt11,
        amount_sat=amount_sat,
        operations_amount_sat=operations_amount_sat,
        prize_pool_amount_sat=prize_pool_amount_sat,
        lnbits_tribute_amount_sat=lnbits_tribute_amount_sat,
        status="pending",
        claim_token=claim_token,
    )
    await create_payment_request(record)
    await create_audit_event(world.id, "claim_requested", record.id, payload={"display_name": data.display_name})
    await publish_public_event(world.id, event="claim_requested", payment_request_id=record.id)
    return PaymentRequestResponse(
        payment_request_id=record.id,
        payment_hash=record.payment_hash,
        payment_request=payment.bolt11,
        amount_sat=amount_sat,
        claim_token=claim_token,
    )


async def get_claim_status(payment_request_id: str) -> PaymentStatusResponse:
    payment_request = await get_payment_request(payment_request_id)
    if not payment_request:
        raise ValueError("Payment request not found.")
    return PaymentStatusResponse(
        payment_request_id=payment_request.id,
        payment_hash=payment_request.payment_hash,
        status=payment_request.status,
        paid_at=payment_request.paid_at,
    )


async def reveal_claim_credentials(claim_token: str) -> AgentCredentialReveal:
    lock = reveal_locks.setdefault(claim_token, asyncio.Lock())
    async with lock:
        payment_request = await get_payment_request_by_claim_token(claim_token)
        if not payment_request:
            raise ValueError("Claim token not found.")
        if payment_request.status != "paid":
            raise ValueError("Payment is not settled yet.")
        if payment_request.credentials_revealed:
            raise ValueError("Credentials already revealed.")
        if not payment_request.agent_id or not payment_request.business_id:
            raise ValueError("Claim is not ready.")
        agent = await get_agent(payment_request.agent_id)
        if not agent:
            raise ValueError("Claim agent not found.")
        api_key = generate_api_key()
        await update_agent(agent.copy(update={"api_key_hash": hash_api_key(api_key)}))
        updated = await update_payment_request(
            payment_request.copy(
                update={"credentials_revealed": True, "issued_api_key": None}
            )
        )
        await create_audit_event(updated.world_id, "credentials_revealed", updated.id)
        return AgentCredentialReveal(
            agent_id=updated.agent_id or "",
            business_id=updated.business_id or "",
            api_key=api_key,
            display_name=updated.display_name,
            payment_status=updated.status,
        )


async def get_agent_session(world_id: str, api_key: str) -> AgentSession:
    from .crud import get_agent_by_api_key

    agent = await get_agent_by_api_key(world_id, api_key)
    if not agent:
        raise ValueError("Invalid API key.")
    business = await get_active_business_for_agent(agent.id)
    if not business:
        raise ValueError("No active business for agent.")
    world = await get_world_by_id(world_id)
    if not world:
        raise ValueError("World not found.")
    current_epoch = await ensure_current_epoch(world)
    if not current_epoch:
        raise ValueError("World is idle until the first business opens.")
    latest_submission = await get_latest_submission_for_business(world_id, business.id)
    snapshots = await list_snapshots_for_business(business.id, limit=10)
    return AgentSession(
        agent=to_safe_agent(agent),
        business=business,
        current_epoch=current_epoch,
        latest_submission=latest_submission,
        recent_snapshots=snapshots,
    )


def validate_submission(epoch: Epoch, business: Business, payload: ActionPayload, now: datetime | None = None) -> str | None:
    now = now or utc_now()
    if business.status == "closed":
        return "Business is closed."
    if payload.epoch != epoch.epoch_number:
        return "Submission epoch does not match the current epoch."
    if payload.business_id != business.id:
        return "Submission business does not match the active business."
    if now > epoch.submission_deadline_at:
        return "Submission cutoff has passed."
    if payload.restock_units < 0 or payload.maintenance_budget_sat < 0 or payload.quality_budget_sat < 0:
        return "Submission values must be non-negative."
    if payload.price_sat < 1:
        return "Price must be at least 1 sat."
    return None


async def submit_action(world_id: str, api_key: str, payload: ActionPayload) -> SubmissionAccepted:
    session = await get_agent_session(world_id, api_key)
    error = validate_submission(session.current_epoch, session.business, payload)
    replaced_previous = (
        await get_effective_submission_for_epoch(world_id, payload.epoch, session.business.id)
    ) is not None
    submission = await create_submission(
        world_id=world_id,
        epoch_number=payload.epoch,
        business_id=session.business.id,
        payload=payload,
        is_valid=error is None,
        validation_error=error,
    )
    await create_audit_event(world_id, "submission_created", submission.id, payload={"valid": error is None})
    return SubmissionAccepted(
        submission_id=submission.id,
        world_id=world_id,
        epoch_number=payload.epoch,
        business_id=session.business.id,
        accepted=error is None,
        replaced_previous=replaced_previous,
        validation_error=error,
        submitted_at=submission.submitted_at,
    )


def _reliability_delta(spend: int) -> float:
    if spend <= 0:
        return -0.04
    if spend <= 4:
        return -0.01
    if spend <= 7:
        return 0.01
    return 0.02


def _quality_delta(spend: int) -> float:
    if spend <= 0:
        return -0.02
    if spend <= 3:
        return 0.0
    if spend <= 6:
        return 0.01
    return 0.02


def _price_score(price_sat: int, district: District, business_type_price_floor: int) -> float:
    ratio = price_sat / max(1, business_type_price_floor)
    return clamp(1.6 - (ratio * district.price_sensitivity * 0.5), 0.1, 1.5)


def _effective_event_multiplier(world: World, district: District) -> float:
    base = world.active_event_multiplier if world.active_event_remaining_epochs > 0 else 1.0
    return base


async def resolve_epoch(world_id: str, epoch_number: int | None = None) -> Epoch:
    lock = runtime_locks.setdefault(world_id, asyncio.Lock())
    async with lock:
        world = await get_world_by_id(world_id)
        if not world:
            raise ValueError("World not found.")
        world = await ensure_runtime_world_state(world)
        if world.current_epoch_number <= 0:
            raise ValueError("World is idle until the first business opens.")
        target_epoch_number = epoch_number if epoch_number is not None else world.current_epoch_number
        epoch = await get_epoch(world.id, target_epoch_number)
        if not epoch:
            await ensure_current_epoch(world)
            epoch = await get_epoch(world.id, target_epoch_number)
        if not epoch:
            raise ValueError("Epoch not found.")
        if epoch.resolved_at:
            return epoch

        districts = {item.id: item for item in await list_districts(world.id)}
        business_types = {item.id: item for item in await list_business_types(world.id)}
        businesses = [item for item in await list_businesses(world.id) if item.status != "closed"]
        by_district: dict[str, list[Business]] = {}
        for business in businesses:
            by_district.setdefault(business.district_id, []).append(business)

        snapshot_count = 0
        for district_id, district_businesses in by_district.items():
            district = districts.get(district_id)
            if not district:
                continue
            event_multiplier = _effective_event_multiplier(world, district)
            demand = max(0, math.floor(district.footfall_base * event_multiplier))
            scores: dict[str, float] = {}
            payloads: dict[str, ActionPayload | None] = {}
            for business in district_businesses:
                business_type = business_types.get(business.business_type_id)
                if not business_type:
                    continue
                submission = await get_effective_submission_for_epoch(world.id, epoch.epoch_number, business.id)
                payload = submission.payload if submission else None
                payloads[business.id] = payload
                price_sat = payload.price_sat if payload else business.price_sat
                scores[business.id] = (
                    0.30 * _price_score(price_sat, district, business_type.base_unit_cost_sat * 2)
                    + 0.20 * clamp(business.quality_level, 0, 1.5)
                    + 0.20 * clamp(business.reputation, 0, 1.5)
                    + 0.15 * clamp(business.reliability, 0, 1.5)
                    + 0.15 * 1.0
                )

            total_scores = max(0.01, sum(scores.values()))
            for business in district_businesses:
                business_type = business_types.get(business.business_type_id)
                if not business_type:
                    continue
                payload = payloads.get(business.id)
                price_sat = payload.price_sat if payload else business.price_sat
                restock_units = payload.restock_units if payload else 0
                maintenance_budget_sat = payload.maintenance_budget_sat if payload else 0
                quality_budget_sat = payload.quality_budget_sat if payload else 0
                stock_before = business.stock_units
                cash_before = business.cash_sat
                reputation_before = business.reputation
                reliability_before = business.reliability
                quality_before = business.quality_level
                restock_cost = restock_units * business_type.base_unit_cost_sat
                stock_after_restock = stock_before + restock_units
                cash_after_restock = cash_before - restock_cost
                capacity = max(
                    0,
                    math.floor(
                        business_type.base_capacity_units * (0.7 + (0.6 * business.reliability))
                    ),
                )
                allocated = math.floor(demand * (scores.get(business.id, 0.0) / total_scores))
                units_sold = min(allocated, stock_after_restock, capacity)
                revenue_sat = units_sold * price_sat
                profit_sat = revenue_sat - business_type.fixed_rent_sat - maintenance_budget_sat - quality_budget_sat
                stock_after = max(0, stock_after_restock - units_sold)
                cash_after = cash_after_restock + profit_sat
                reliability_after = clamp(
                    reliability_before + _reliability_delta(maintenance_budget_sat), 0.0, 1.5
                )
                quality_after = clamp(
                    quality_before + _quality_delta(quality_budget_sat), 0.0, 1.5
                )
                reputation_after = reputation_before
                if units_sold < allocated:
                    reputation_after -= 0.03
                else:
                    reputation_after += 0.01
                if payload is None:
                    reputation_after -= 0.01
                if price_sat > (business_type.base_unit_cost_sat * 4) and quality_after < 0.5:
                    reputation_after -= 0.02
                reputation_after = clamp(reputation_after, 0.0, 1.5)
                status = business.status
                missed_epochs = business.missed_epochs + (0 if payload else 1)
                distress_epochs = business.distress_epochs
                closed_at = business.closed_at
                if cash_after < -100:
                    status = "distress"
                    distress_epochs += 1
                elif status != "closed":
                    status = "active"
                    distress_epochs = 0
                if distress_epochs >= 3:
                    status = "closed"
                    closed_at = utc_now()
                updated_business = business.copy(
                    update={
                        "price_sat": price_sat,
                        "stock_units": stock_after,
                        "cash_sat": cash_after,
                        "reputation": reputation_after,
                        "reliability": reliability_after,
                        "quality_level": quality_after,
                        "status": status,
                        "missed_epochs": missed_epochs,
                        "distress_epochs": distress_epochs,
                        "closed_at": closed_at,
                    }
                )
                await update_business(updated_business)
                await create_snapshot(
                    BusinessEpochSnapshot(
                        id=token_urlsafe(12),
                        world_id=world.id,
                        epoch_number=epoch.epoch_number,
                        business_id=business.id,
                        units_sold=units_sold,
                        revenue_sat=revenue_sat,
                        profit_sat=profit_sat,
                        stock_before=stock_before,
                        stock_after=stock_after,
                        cash_before=cash_before,
                        cash_after=cash_after,
                        reputation_before=reputation_before,
                        reputation_after=reputation_after,
                        reliability_before=reliability_before,
                        reliability_after=reliability_after,
                        quality_before=quality_before,
                        quality_after=quality_after,
                    )
                )
                snapshot_count += 1

        board = await build_business_board(world)
        top_names = ", ".join([item.display_name for item in board[:3]]) or "No active businesses"
        digest_text = f"Epoch {epoch.epoch_number} resolved. Leaders: {top_names}."
        updated_epoch = await update_epoch(
            epoch.copy(
                update={
                    "status": "resolved",
                    "resolved_at": utc_now(),
                    "digest_text": digest_text,
                    "event_summary_text": world.active_event_name,
                }
            )
        )
        event_remaining = max(0, world.active_event_remaining_epochs - 1)
        current_epoch_number = max(world.current_epoch_number, current_utc_epoch_number(world))
        event_update = {
            "last_resolved_epoch": epoch.epoch_number,
            "last_digest_text": digest_text,
            "current_epoch_number": current_epoch_number,
            "current_season_number": season_number_for_epoch(world, current_epoch_number),
            "active_event_remaining_epochs": event_remaining,
        }
        if event_remaining == 0:
            event_update.update(
                {
                    "active_event_id": None,
                    "active_event_name": None,
                    "active_event_multiplier": 1.0,
                }
            )
        world = await update_world(world.copy(update=event_update))
        if epoch.epoch_number % world.season_length_epochs == 0:
            leaderboard = build_leaderboard(board)
            leaderboard_payload = json.dumps([item.dict() for item in leaderboard])
            season_result = await create_season_result(
                SeasonResult(
                    id=token_urlsafe(12),
                    world_id=world.id,
                    season_number=epoch.season_number,
                    epoch_start=max(0, epoch.epoch_number - world.season_length_epochs + 1),
                    epoch_end=epoch.epoch_number,
                    leaderboard_text=leaderboard_payload,
                    payout_status="pending",
                    payout_summary_text="Season completed. Reward settlement pending.",
                )
            )
            await settle_season_payouts(world, season_result, leaderboard)
            await retire_season_businesses(world, season_result)
            current_epoch_number = epoch.epoch_number
            world = await update_world(
                world.copy(
                    update={
                        "current_epoch_number": current_epoch_number,
                        "current_season_number": season_number_for_epoch(world, current_epoch_number),
                        "active_event_id": None,
                        "active_event_name": None,
                        "active_event_multiplier": 1.0,
                        "active_event_remaining_epochs": 0,
                    }
                )
            )
        await create_audit_event(world.id, "epoch_resolved", updated_epoch.id, payload={"snapshot_count": snapshot_count})
        await publish_public_event(world.id, event="epoch_resolved", epoch_number=updated_epoch.epoch_number)
        await publish_admin_event(world.id, scope="epochs", event="resolved", entity_id=updated_epoch.id)
        return updated_epoch


async def maybe_resolve_due_epochs() -> None:
    now = utc_now()
    from .crud import list_worlds

    for world in await list_worlds():
        if world.status != "active":
            continue
        current_epoch = await ensure_current_epoch(world)
        if not current_epoch:
            continue
        due_epochs = await list_unresolved_epochs_before(world.id, now)
        for epoch in due_epochs:
            try:
                await resolve_epoch(world.id, epoch.epoch_number)
            except Exception as exc:
                logger.warning(f"Failed resolving Market Town epoch {epoch.id}: {exc}")


async def payment_received_for_claim(payment: Payment) -> bool:
    payment_hash = payment.payment_hash
    lock = settlement_locks.setdefault(payment_hash, asyncio.Lock())
    async with lock:
        record = await get_payment_request_by_hash(payment_hash)
        if not record:
            logger.warning(f"No Market Town payment request found for hash {payment_hash}")
            return False
        if record.status == "paid":
            return True
        if record.status not in ("pending", "settling"):
            return False

        world = await get_world_by_id(record.world_id)
        district = await get_district(record.district_id)
        business_type = await get_business_type(record.business_type_id)
        if not world or not district or not business_type:
            logger.warning("Market Town payment request has missing world configuration.")
            return False

        used_slots = await get_active_business_count_for_district(world.id, district.id)
        if used_slots >= district.slot_limit:
            updated = await update_payment_request(
                record.copy(update={"status": "paid_unclaimed", "paid_at": utc_now()})
            )
            await create_audit_event(
                world.id,
                "claim_paid_unclaimed",
                updated.id,
                payload={"reason": "district_full"},
            )
            await publish_payment_event(
                updated.payment_hash,
                {
                    "pending": False,
                    "status": updated.status,
                    "payment_request_id": updated.id,
                },
            )
            await publish_admin_event(
                world.id,
                scope="payments",
                event="paid_unclaimed",
                entity_id=updated.id,
            )
            return False

        had_active_businesses = await world_has_active_businesses(world.id)
        placeholder_secret = token_urlsafe(32)
        agent = await create_agent(
            world_id=world.id,
            display_name=record.display_name,
            api_key_hash=hash_api_key(placeholder_secret),
            payout_lnaddress=record.payout_lnaddress,
        )
        business = await create_business(
            world_id=world.id,
            agent_id=agent.id,
            business_type_id=business_type.id,
            district_id=district.id,
            display_name=record.display_name,
            price_sat=max(1, business_type.base_unit_cost_sat * 2),
        )
        updated = await update_payment_request(
            record.copy(
                update={
                    "status": "paid",
                    "paid_at": utc_now(),
                    "agent_id": agent.id,
                    "business_id": business.id,
                    "issued_api_key": None,
                }
            )
        )
        if updated.operations_amount_sat > 0:
            try:
                await settle_operator_fee(
                    updated.operations_amount_sat,
                    world.wallet_id,
                    world.fee_wallet_id,
                    world.id,
                )
            except Exception as exc:
                logger.warning(f"Market Town operator fee settlement failed for {updated.id}: {exc}")
        if updated.lnbits_tribute_amount_sat > 0:
            try:
                await pay_tribute(updated.lnbits_tribute_amount_sat, world.wallet_id)
            except Exception as exc:
                logger.warning(f"Market Town tribute payment failed for {updated.id}: {exc}")
        if not had_active_businesses:
            next_epoch_number = max(1, world.last_resolved_epoch + 1)
            world = await update_world(
                world.copy(
                    update={
                        "started_at": world_started_at_for_epoch(world, next_epoch_number, utc_now()),
                        "current_epoch_number": 0,
                        "current_season_number": season_number_for_epoch(world, next_epoch_number),
                    }
                )
            )
            await ensure_current_epoch(world)
        await create_audit_event(
            world.id,
            "claim_paid",
            updated.id,
            payload={"agent_id": agent.id, "business_id": business.id},
        )
        await publish_payment_event(
            updated.payment_hash,
            {
                "pending": False,
                "status": updated.status,
                "payment_request_id": updated.id,
            },
        )
        await publish_public_event(world.id, event="claim_paid", payment_request_id=updated.id)
        await publish_admin_event(
            world.id,
            scope="payments",
            event="paid",
            entity_id=updated.id,
        )
        return True


async def reset_world_seeds(world: World) -> None:
    await seed_defaults(world.id, replace=True)
    await create_audit_event(world.id, "seed_reset", world.id)


async def update_district_settings(district: District, data: UpdateDistrict) -> District:
    updated = await update_district(district.copy(update=data.dict(exclude_unset=True)))
    await create_audit_event(updated.world_id, "district_updated", updated.id)
    return updated


async def update_business_type_settings(business_type, data: UpdateBusinessType):
    updated = await update_business_type(
        business_type.copy(update=data.dict(exclude_unset=True))
    )
    await create_audit_event(updated.world_id, "business_type_updated", updated.id)
    return updated


async def update_agent_status(agent, status: str):
    updated = await update_agent(agent.copy(update={"status": status}))
    await create_audit_event(updated.world_id, "agent_updated", updated.id, payload={"status": status})
    return updated


async def override_business_status(business: Business, status: str) -> Business:
    updated = await update_business(
        business.copy(update={"status": status, "closed_at": utc_now() if status == "closed" else None})
    )
    await create_audit_event(updated.world_id, "business_updated", updated.id, payload={"status": status})
    return updated
