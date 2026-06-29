import json
from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import (
    ActionPayload,
    Agent,
    AuditEvent,
    Business,
    BusinessEpochSnapshot,
    BusinessType,
    CreateBusinessType,
    CreateDistrict,
    CreateWorld,
    District,
    Epoch,
    PaymentRequestRecord,
    SeasonResult,
    Submission,
    SubmissionView,
    World,
    utc_now,
)

db = Database("ext_market_town")


def hash_api_key(api_key: str) -> str:
    return sha256(api_key.encode()).hexdigest()


def generate_api_key() -> str:
    return token_urlsafe(32)


def _ensure_utc(value: datetime | float | int | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_submission_view(row: dict) -> SubmissionView:
    payload = dict(row)
    payload["payload"] = ActionPayload.parse_obj(json.loads(payload.pop("payload_text")))
    payload["submitted_at"] = _ensure_utc(payload.get("submitted_at"))
    return SubmissionView.parse_obj(payload)


async def create_world(user_id: str, data: CreateWorld) -> World:
    now = utc_now()
    world = World(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name=data.name,
        status=data.status,
        wallet_id=data.wallet_id,
        fee_wallet_id=data.fee_wallet_id,
        operator_fee_percent=data.operator_fee_percent,
        world_seed=data.world_seed or token_urlsafe(16),
        epoch_duration_hours=data.epoch_duration_hours,
        submission_cutoff_minutes=data.submission_cutoff_minutes,
        season_length_epochs=data.season_length_epochs,
        current_epoch_number=0,
        current_season_number=1,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    await db.insert("market_town.worlds", world)
    return world


async def get_world_for_user(user_id: str) -> World | None:
    return await db.fetchone(
        "SELECT * FROM market_town.worlds WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1",
        {"user_id": user_id},
        World,
    )


async def get_world_by_id(world_id: str) -> World | None:
    return await db.fetchone(
        "SELECT * FROM market_town.worlds WHERE id = :id",
        {"id": world_id},
        World,
    )


async def update_world(world: World) -> World:
    updated = world.copy(update={"updated_at": utc_now()})
    await db.update("market_town.worlds", updated)
    return updated


async def delete_world(world_id: str) -> None:
    for table in (
        "audit_events",
        "payment_requests",
        "season_results",
        "business_epoch_snapshots",
        "submissions",
        "epochs",
        "businesses",
        "agents",
        "business_types",
        "world_districts",
    ):
        await db.execute(f"DELETE FROM market_town.{table} WHERE world_id = :world_id", {"world_id": world_id})
    await db.execute("DELETE FROM market_town.worlds WHERE id = :world_id", {"world_id": world_id})


async def create_district(world_id: str, data: CreateDistrict) -> District:
    now = utc_now()
    district = District(
        id=urlsafe_short_hash(),
        world_id=world_id,
        district_key=data.district_key,
        name=data.name,
        footfall_base=data.footfall_base,
        affluence=data.affluence,
        price_sensitivity=data.price_sensitivity,
        quality_preference=data.quality_preference,
        slot_limit=data.slot_limit,
        config_text=data.config_text,
        created_at=now,
        updated_at=now,
    )
    await db.insert("market_town.world_districts", district)
    return district


async def get_district(district_id: str) -> District | None:
    return await db.fetchone(
        "SELECT * FROM market_town.world_districts WHERE id = :id",
        {"id": district_id},
        District,
    )


async def get_district_by_key(world_id: str, district_key: str) -> District | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.world_districts
        WHERE world_id = :world_id AND district_key = :district_key
        LIMIT 1
        """,
        {"world_id": world_id, "district_key": district_key},
        District,
    )


async def list_districts(world_id: str) -> list[District]:
    return await db.fetchall(
        "SELECT * FROM market_town.world_districts WHERE world_id = :world_id ORDER BY name ASC",
        {"world_id": world_id},
        District,
    )


async def update_district(district: District) -> District:
    updated = district.copy(update={"updated_at": utc_now()})
    await db.update("market_town.world_districts", updated)
    return updated


async def delete_districts_for_world(world_id: str) -> None:
    await db.execute("DELETE FROM market_town.world_districts WHERE world_id = :world_id", {"world_id": world_id})


async def create_business_type(world_id: str, data: CreateBusinessType) -> BusinessType:
    now = utc_now()
    business_type = BusinessType(
        id=urlsafe_short_hash(),
        world_id=world_id,
        type_key=data.type_key,
        name=data.name,
        category=data.category,
        open_fee_sat=data.open_fee_sat,
        base_unit_cost_sat=data.base_unit_cost_sat,
        fixed_rent_sat=data.fixed_rent_sat,
        base_capacity_units=data.base_capacity_units,
        config_text=data.config_text,
        created_at=now,
        updated_at=now,
    )
    await db.insert("market_town.business_types", business_type)
    return business_type


async def get_business_type(business_type_id: str) -> BusinessType | None:
    return await db.fetchone(
        "SELECT * FROM market_town.business_types WHERE id = :id",
        {"id": business_type_id},
        BusinessType,
    )


async def get_business_type_by_key(world_id: str, type_key: str) -> BusinessType | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.business_types
        WHERE world_id = :world_id AND type_key = :type_key
        LIMIT 1
        """,
        {"world_id": world_id, "type_key": type_key},
        BusinessType,
    )


async def list_business_types(world_id: str) -> list[BusinessType]:
    return await db.fetchall(
        "SELECT * FROM market_town.business_types WHERE world_id = :world_id ORDER BY name ASC",
        {"world_id": world_id},
        BusinessType,
    )


async def update_business_type(business_type: BusinessType) -> BusinessType:
    updated = business_type.copy(update={"updated_at": utc_now()})
    await db.update("market_town.business_types", updated)
    return updated


async def delete_business_types_for_world(world_id: str) -> None:
    await db.execute(
        "DELETE FROM market_town.business_types WHERE world_id = :world_id",
        {"world_id": world_id},
    )


async def create_agent(
    world_id: str,
    display_name: str,
    api_key_hash: str,
    payout_lnaddress: str,
) -> Agent:
    now = utc_now()
    agent = Agent(
        id=urlsafe_short_hash(),
        world_id=world_id,
        display_name=display_name,
        api_key_hash=api_key_hash,
        payout_lnaddress=payout_lnaddress,
        status="active",
        last_claimed_at=now,
        last_opened_at=now,
        created_at=now,
        updated_at=now,
    )
    await db.insert("market_town.agents", agent)
    return agent


async def delete_agent(agent_id: str) -> None:
    await db.execute("DELETE FROM market_town.agents WHERE id = :agent_id", {"agent_id": agent_id})


async def get_agent(agent_id: str) -> Agent | None:
    return await db.fetchone(
        "SELECT * FROM market_town.agents WHERE id = :id",
        {"id": agent_id},
        Agent,
    )


async def get_agent_by_api_key(world_id: str, api_key: str) -> Agent | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.agents
        WHERE world_id = :world_id AND api_key_hash = :api_key_hash AND status != 'inactive'
        LIMIT 1
        """,
        {"world_id": world_id, "api_key_hash": hash_api_key(api_key)},
        Agent,
    )


async def list_agents(world_id: str) -> list[Agent]:
    return await db.fetchall(
        "SELECT * FROM market_town.agents WHERE world_id = :world_id ORDER BY created_at DESC",
        {"world_id": world_id},
        Agent,
    )


async def update_agent(agent: Agent) -> Agent:
    updated = agent.copy(update={"updated_at": utc_now()})
    await db.update("market_town.agents", updated)
    return updated


async def create_business(
    world_id: str,
    agent_id: str,
    business_type_id: str,
    district_id: str,
    display_name: str,
    price_sat: int,
) -> Business:
    now = utc_now()
    business = Business(
        id=urlsafe_short_hash(),
        world_id=world_id,
        agent_id=agent_id,
        business_type_id=business_type_id,
        district_id=district_id,
        display_name=display_name,
        price_sat=price_sat,
        created_at=now,
        updated_at=now,
    )
    await db.insert("market_town.businesses", business)
    return business


async def delete_business(business_id: str) -> None:
    await db.execute(
        "DELETE FROM market_town.businesses WHERE id = :business_id",
        {"business_id": business_id},
    )


async def get_business(business_id: str) -> Business | None:
    return await db.fetchone(
        "SELECT * FROM market_town.businesses WHERE id = :id",
        {"id": business_id},
        Business,
    )


async def get_active_business_for_agent(agent_id: str) -> Business | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.businesses
        WHERE agent_id = :agent_id AND status != 'closed'
        ORDER BY created_at DESC LIMIT 1
        """,
        {"agent_id": agent_id},
        Business,
    )


async def list_businesses(world_id: str) -> list[Business]:
    return await db.fetchall(
        "SELECT * FROM market_town.businesses WHERE world_id = :world_id ORDER BY created_at DESC",
        {"world_id": world_id},
        Business,
    )


async def update_business(business: Business) -> Business:
    updated = business.copy(update={"updated_at": utc_now()})
    await db.update("market_town.businesses", updated)
    return updated


async def get_active_business_count_for_district(world_id: str, district_id: str) -> int:
    row: dict | None = await db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM market_town.businesses
        WHERE world_id = :world_id AND district_id = :district_id AND status != 'closed'
        """,
        {"world_id": world_id, "district_id": district_id},
    )
    return int((row or {}).get("count") or 0)


async def create_epoch(epoch: Epoch) -> Epoch:
    await db.insert("market_town.epochs", epoch)
    return epoch


async def get_epoch(world_id: str, epoch_number: int) -> Epoch | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.epochs
        WHERE world_id = :world_id AND epoch_number = :epoch_number
        LIMIT 1
        """,
        {"world_id": world_id, "epoch_number": epoch_number},
        Epoch,
    )


async def claim_epoch_for_resolution(world_id: str, epoch_number: int, stale_before: datetime) -> bool:
    result = await db.execute(
        f"""
        UPDATE market_town.epochs
        SET status = 'resolving',
            updated_at = {db.timestamp_placeholder("now")}
        WHERE world_id = :world_id
          AND epoch_number = :epoch_number
          AND resolved_at IS NULL
          AND (
            status = 'open'
            OR (
              status = 'resolving'
              AND updated_at <= {db.timestamp_placeholder("stale_before")}
            )
          )
        """,
        {
            "world_id": world_id,
            "epoch_number": epoch_number,
            "now": utc_now().timestamp(),
            "stale_before": stale_before.timestamp(),
        },
    )
    return bool(result.rowcount)


async def get_latest_epoch(world_id: str) -> Epoch | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.epochs
        WHERE world_id = :world_id
        ORDER BY epoch_number DESC LIMIT 1
        """,
        {"world_id": world_id},
        Epoch,
    )


async def list_epochs(world_id: str, limit: int = 20) -> list[Epoch]:
    rows = await db.fetchall(
        f"""
        SELECT * FROM market_town.epochs
        WHERE world_id = :world_id
        ORDER BY epoch_number DESC LIMIT {int(limit)}
        """,
        {"world_id": world_id},
        Epoch,
    )
    return rows


async def list_unresolved_epochs_before(world_id: str, before_time: datetime) -> list[Epoch]:
    return await db.fetchall(
        f"""
        SELECT * FROM market_town.epochs
        WHERE world_id = :world_id
          AND resolved_at IS NULL
          AND digest_at <= {db.timestamp_placeholder("before_time")}
        ORDER BY epoch_number ASC
        """,
        {"world_id": world_id, "before_time": before_time.timestamp()},
        Epoch,
    )


async def update_epoch(epoch: Epoch) -> Epoch:
    updated = epoch.copy(update={"updated_at": utc_now()})
    await db.update("market_town.epochs", updated)
    return updated


async def create_submission(
    world_id: str,
    epoch_number: int,
    business_id: str,
    payload: ActionPayload,
    is_valid: bool = True,
    validation_error: str | None = None,
) -> Submission:
    submission = Submission(
        id=urlsafe_short_hash(),
        world_id=world_id,
        epoch_number=epoch_number,
        business_id=business_id,
        payload_text=payload.json(),
        is_valid=is_valid,
        validation_error=validation_error,
        submitted_at=utc_now(),
    )
    await db.insert("market_town.submissions", submission)
    return submission


async def list_submissions(world_id: str, limit: int = 50) -> list[SubmissionView]:
    rows: list[dict] = await db.fetchall(
        f"""
        SELECT * FROM market_town.submissions
        WHERE world_id = :world_id
        ORDER BY submitted_at DESC LIMIT {int(limit)}
        """,
        {"world_id": world_id},
    )
    return [_to_submission_view(row) for row in rows]


async def list_submissions_for_epoch(world_id: str, epoch_number: int) -> list[SubmissionView]:
    rows: list[dict] = await db.fetchall(
        """
        SELECT * FROM market_town.submissions
        WHERE world_id = :world_id AND epoch_number = :epoch_number
        ORDER BY submitted_at DESC
        """,
        {"world_id": world_id, "epoch_number": epoch_number},
    )
    return [_to_submission_view(row) for row in rows]


async def get_latest_submission_for_business(world_id: str, business_id: str) -> SubmissionView | None:
    row: dict | None = await db.fetchone(
        """
        SELECT * FROM market_town.submissions
        WHERE world_id = :world_id AND business_id = :business_id
        ORDER BY submitted_at DESC LIMIT 1
        """,
        {"world_id": world_id, "business_id": business_id},
    )
    return _to_submission_view(row) if row else None


async def get_effective_submission_for_epoch(
    world_id: str, epoch_number: int, business_id: str
) -> SubmissionView | None:
    row: dict | None = await db.fetchone(
        """
        SELECT * FROM market_town.submissions
        WHERE world_id = :world_id
          AND epoch_number = :epoch_number
          AND business_id = :business_id
          AND is_valid = :is_valid
        ORDER BY submitted_at DESC LIMIT 1
        """,
        {
            "world_id": world_id,
            "epoch_number": epoch_number,
            "business_id": business_id,
            "is_valid": True,
        },
    )
    return _to_submission_view(row) if row else None


async def create_snapshot(snapshot: BusinessEpochSnapshot) -> BusinessEpochSnapshot:
    await db.insert("market_town.business_epoch_snapshots", snapshot)
    return snapshot


async def get_snapshot_for_business_epoch(
    world_id: str, epoch_number: int, business_id: str
) -> BusinessEpochSnapshot | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.business_epoch_snapshots
        WHERE world_id = :world_id
          AND epoch_number = :epoch_number
          AND business_id = :business_id
        LIMIT 1
        """,
        {
            "world_id": world_id,
            "epoch_number": epoch_number,
            "business_id": business_id,
        },
        BusinessEpochSnapshot,
    )


async def list_snapshots_for_business(business_id: str, limit: int = 10) -> list[BusinessEpochSnapshot]:
    return await db.fetchall(
        f"""
        SELECT * FROM market_town.business_epoch_snapshots
        WHERE business_id = :business_id
        ORDER BY epoch_number DESC LIMIT {int(limit)}
        """,
        {"business_id": business_id},
        BusinessEpochSnapshot,
    )


async def create_season_result(season_result: SeasonResult) -> SeasonResult:
    await db.insert("market_town.season_results", season_result)
    return season_result


async def get_season_result(world_id: str, season_number: int) -> SeasonResult | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.season_results
        WHERE world_id = :world_id AND season_number = :season_number
        LIMIT 1
        """,
        {"world_id": world_id, "season_number": season_number},
        SeasonResult,
    )


async def update_season_result(season_result: SeasonResult) -> SeasonResult:
    updated = season_result.copy(update={"updated_at": utc_now()})
    await db.update("market_town.season_results", updated)
    return updated


async def list_season_results(world_id: str) -> list[SeasonResult]:
    return await db.fetchall(
        """
        SELECT * FROM market_town.season_results
        WHERE world_id = :world_id
        ORDER BY season_number DESC
        """,
        {"world_id": world_id},
        SeasonResult,
    )


async def list_paid_payment_requests_for_season(
    world_id: str,
    season_started_at: datetime,
    season_ended_at: datetime,
    *,
    include_before_start: bool = False,
) -> list[PaymentRequestRecord]:
    lower_clause = "" if include_before_start else f"AND paid_at >= {db.timestamp_placeholder('season_started_at')}"
    return await db.fetchall(
        f"""
        SELECT * FROM market_town.payment_requests
        WHERE world_id = :world_id
          AND status = 'paid'
          AND paid_at IS NOT NULL
          {lower_clause}
          AND paid_at <= {db.timestamp_placeholder("season_ended_at")}
        ORDER BY paid_at ASC
        """,
        {
            "world_id": world_id,
            "season_started_at": season_started_at.timestamp(),
            "season_ended_at": season_ended_at.timestamp(),
        },
        PaymentRequestRecord,
    )


async def create_payment_request(payment_request: PaymentRequestRecord) -> PaymentRequestRecord:
    await db.insert("market_town.payment_requests", payment_request)
    return payment_request


async def get_payment_request(payment_request_id: str) -> PaymentRequestRecord | None:
    return await db.fetchone(
        "SELECT * FROM market_town.payment_requests WHERE id = :id",
        {"id": payment_request_id},
        PaymentRequestRecord,
    )


async def get_payment_request_by_hash(payment_hash: str) -> PaymentRequestRecord | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.payment_requests
        WHERE payment_hash = :payment_hash
        LIMIT 1
        """,
        {"payment_hash": payment_hash},
        PaymentRequestRecord,
    )


async def claim_payment_request_for_settlement(
    payment_hash: str, stale_before: datetime
) -> PaymentRequestRecord | None:
    result = await db.execute(
        f"""
        UPDATE market_town.payment_requests
        SET status = 'settling',
            updated_at = {db.timestamp_placeholder("now")}
        WHERE payment_hash = :payment_hash
          AND (
            status = 'pending'
            OR status = 'expired'
            OR (
              status = 'settling'
              AND updated_at <= {db.timestamp_placeholder("stale_before")}
            )
          )
        """,
        {
            "payment_hash": payment_hash,
            "now": utc_now().timestamp(),
            "stale_before": stale_before.timestamp(),
        },
    )
    if not result.rowcount:
        return None
    return await get_payment_request_by_hash(payment_hash)


async def get_payment_request_by_claim_token(claim_token: str) -> PaymentRequestRecord | None:
    return await db.fetchone(
        """
        SELECT * FROM market_town.payment_requests
        WHERE claim_token = :claim_token
        LIMIT 1
        """,
        {"claim_token": claim_token},
        PaymentRequestRecord,
    )


async def claim_payment_request_credentials_reveal(
    claim_token: str,
) -> PaymentRequestRecord | None:
    result = await db.execute(
        f"""
        UPDATE market_town.payment_requests
        SET credentials_revealed = TRUE,
            issued_api_key = NULL,
            updated_at = {db.timestamp_placeholder("now")}
        WHERE claim_token = :claim_token
          AND status = 'paid'
          AND credentials_revealed = FALSE
          AND agent_id IS NOT NULL
          AND business_id IS NOT NULL
        """,
        {"claim_token": claim_token, "now": utc_now().timestamp()},
    )
    if not result.rowcount:
        return None
    return await get_payment_request_by_claim_token(claim_token)


async def reset_payment_request_credentials_reveal(claim_token: str) -> None:
    await db.execute(
        f"""
        UPDATE market_town.payment_requests
        SET credentials_revealed = FALSE,
            updated_at = {db.timestamp_placeholder("now")}
        WHERE claim_token = :claim_token
          AND credentials_revealed = TRUE
        """,
        {"claim_token": claim_token, "now": utc_now().timestamp()},
    )


async def list_pending_payment_requests(world_id: str) -> list[PaymentRequestRecord]:
    return await db.fetchall(
        """
        SELECT * FROM market_town.payment_requests
        WHERE world_id = :world_id AND status = 'pending'
        ORDER BY created_at DESC
        """,
        {"world_id": world_id},
        PaymentRequestRecord,
    )


async def list_active_pending_payment_requests(world_id: str, before_time: datetime) -> list[PaymentRequestRecord]:
    now = utc_now()
    return await db.fetchall(
        f"""
        SELECT * FROM market_town.payment_requests
        WHERE world_id = :world_id
          AND status = 'pending'
          AND created_at > {db.timestamp_placeholder("before_time")}
          AND (
            reservation_expires_at IS NULL
            OR reservation_expires_at > {db.timestamp_placeholder("now")}
          )
        ORDER BY created_at DESC
        """,
        {
            "world_id": world_id,
            "before_time": before_time.timestamp(),
            "now": now.timestamp(),
        },
        PaymentRequestRecord,
    )


async def expire_pending_payment_requests(world_id: str, before_time: datetime) -> None:
    await db.execute(
        f"""
        UPDATE market_town.payment_requests
        SET status = 'expired',
            updated_at = {db.timestamp_placeholder("now")}
        WHERE world_id = :world_id
          AND status = 'pending'
          AND (
            created_at <= {db.timestamp_placeholder("before_time")}
            OR (
              reservation_expires_at IS NOT NULL
              AND reservation_expires_at <= {db.timestamp_placeholder("now")}
            )
          )
        """,
        {
            "world_id": world_id,
            "now": utc_now().timestamp(),
            "before_time": before_time.timestamp(),
        },
    )


async def update_payment_request(payment_request: PaymentRequestRecord) -> PaymentRequestRecord:
    updated = payment_request.copy(update={"updated_at": utc_now()})
    await db.update("market_town.payment_requests", updated)
    return updated


async def create_audit_event(
    world_id: str,
    event_type: str,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        id=urlsafe_short_hash(),
        world_id=world_id,
        event_type=event_type,
        entity_id=entity_id,
        payload_text=json.dumps(payload or {}),
        created_at=utc_now(),
    )
    await db.insert("market_town.audit_events", event)
    return event


async def list_worlds() -> list[World]:
    return await db.fetchall("SELECT * FROM market_town.worlds", model=World)
