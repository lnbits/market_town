from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketTownBaseModel(BaseModel):
    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class FeeSplit(MarketTownBaseModel):
    operations_percent: float = Field(default=5.0, ge=0, le=100)
    tribute_percent: float = Field(default=2.0, ge=0, le=100)
    prize_pool_percent: float = Field(default=93.0, ge=0, le=100)


class ActiveEvent(MarketTownBaseModel):
    id: str
    name: str
    demand_multiplier: float = Field(default=1.0, gt=0)
    remaining_epochs: int = Field(default=0, ge=0)


class DistrictConfig(MarketTownBaseModel):
    demand_share_bias: float = Field(default=1.0, gt=0)
    event_multiplier_bias: float = Field(default=1.0, gt=0)


class BusinessTypeConfig(MarketTownBaseModel):
    maintenance_floor_sat: int = Field(default=0, ge=0)
    quality_floor_sat: int = Field(default=0, ge=0)


class ActionPayload(BaseModel):
    epoch: int = Field(ge=0)
    business_id: str = Field(min_length=1, max_length=128)
    price_sat: int = Field(ge=1, le=1_000_000)
    restock_units: int = Field(default=0, ge=0, le=100_000)
    maintenance_budget_sat: int = Field(default=0, ge=0, le=1_000_000)
    quality_budget_sat: int = Field(default=0, ge=0, le=1_000_000)

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class LeaderboardEntry(MarketTownBaseModel):
    business_id: str
    agent_id: str
    business_name: str
    district_name: str
    cash_sat: int = 0
    cash_delta_sat: int = 0
    cash_delta_percent: float | None = None
    latest_profit_sat: int = 0
    latest_revenue_sat: int = 0
    latest_units_sold: int = 0
    price_sat: int = 0
    stock_units: int = 0
    reputation: float = 0
    reliability: float = 0
    quality_level: float = 0


class EpochDigest(MarketTownBaseModel):
    world_id: str
    epoch_number: int
    season_number: int
    active_event_name: str | None = None
    resolved_business_count: int = Field(default=0, ge=0)
    top_businesses: list[LeaderboardEntry] = Field(default_factory=list)
    summary: str = ""


############################ World ############################
class CreateWorld(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    wallet_id: str
    fee_wallet_id: str | None = None
    operator_fee_percent: float = Field(default=5.0, ge=0, le=10)
    status: Literal["active", "paused"] = "active"
    epoch_duration_hours: int = Field(default=4, ge=1, le=24)
    submission_cutoff_minutes: int = Field(default=5, ge=1, le=180)
    season_length_epochs: int = Field(default=42, ge=1)
    world_seed: str | None = None


class UpdateWorld(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    wallet_id: str | None = None
    fee_wallet_id: str | None = None
    operator_fee_percent: float | None = Field(default=None, ge=0, le=10)
    status: Literal["active", "paused"] | None = None
    epoch_duration_hours: int | None = Field(default=None, ge=1, le=24)
    submission_cutoff_minutes: int | None = Field(default=None, ge=1, le=180)
    season_length_epochs: int | None = Field(default=None, ge=1)
    world_seed: str | None = None


class World(BaseModel):
    id: str
    user_id: str
    name: str
    status: str = "active"
    wallet_id: str
    fee_wallet_id: str | None = None
    operator_fee_percent: float = 5.0
    world_seed: str
    epoch_duration_hours: int = 4
    submission_cutoff_minutes: int = 5
    season_length_epochs: int = 42
    current_epoch_number: int = 0
    current_season_number: int = 1
    active_event_id: str | None = None
    active_event_name: str | None = None
    active_event_multiplier: float = 1.0
    active_event_remaining_epochs: int = 0
    last_resolved_epoch: int = -1
    last_digest_text: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PublicWorld(BaseModel):
    id: str
    name: str
    status: str
    current_epoch_number: int
    current_season_number: int
    epoch_duration_hours: int
    submission_cutoff_minutes: int
    season_length_epochs: int
    active_event_name: str | None = None
    active_event_multiplier: float = 1.0
    active_event_remaining_epochs: int = 0
    last_digest_text: str | None = None
    started_at: datetime
    updated_at: datetime


class AdminWorld(PublicWorld):
    wallet_id: str
    fee_wallet_id: str | None = None
    operator_fee_percent: float = 5.0


############################ Districts ############################
class CreateDistrict(BaseModel):
    district_key: str
    name: str = Field(min_length=1, max_length=80)
    footfall_base: int = Field(default=100, ge=0)
    affluence: float = Field(default=1.0, ge=0)
    price_sensitivity: float = Field(default=1.0, ge=0)
    quality_preference: float = Field(default=1.0, ge=0)
    slot_limit: int = Field(default=10, ge=1)
    config_text: str | None = Field(default=None, max_length=4096)


class UpdateDistrict(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    footfall_base: int | None = Field(default=None, ge=0)
    affluence: float | None = Field(default=None, ge=0)
    price_sensitivity: float | None = Field(default=None, ge=0)
    quality_preference: float | None = Field(default=None, ge=0)
    slot_limit: int | None = Field(default=None, ge=1)
    config_text: str | None = Field(default=None, max_length=4096)


class District(BaseModel):
    id: str
    world_id: str
    district_key: str
    name: str
    footfall_base: int = 100
    affluence: float = 1.0
    price_sensitivity: float = 1.0
    quality_preference: float = 1.0
    slot_limit: int = 10
    config_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PublicDistrict(BaseModel):
    id: str
    world_id: str
    district_key: str
    name: str
    footfall_base: int = 100
    affluence: float = 1.0
    price_sensitivity: float = 1.0
    quality_preference: float = 1.0
    slot_limit: int = 10
    occupied_slots: int = 0
    pending_slots: int = 0
    available_slots: int = 0


############################ Business Types ############################
class CreateBusinessType(BaseModel):
    type_key: str
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    open_fee_sat: int = Field(default=500, ge=1)
    base_unit_cost_sat: int = Field(default=100, ge=0)
    fixed_rent_sat: int = Field(default=10, ge=0)
    base_capacity_units: int = Field(default=20, ge=0)
    config_text: str | None = Field(default=None, max_length=4096)


class UpdateBusinessType(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    open_fee_sat: int | None = Field(default=None, ge=1)
    base_unit_cost_sat: int | None = Field(default=None, ge=0)
    fixed_rent_sat: int | None = Field(default=None, ge=0)
    base_capacity_units: int | None = Field(default=None, ge=0)
    config_text: str | None = Field(default=None, max_length=4096)


class BusinessType(BaseModel):
    id: str
    world_id: str
    type_key: str
    name: str
    category: str
    open_fee_sat: int = 500
    base_unit_cost_sat: int = 100
    fixed_rent_sat: int = 10
    base_capacity_units: int = 20
    config_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PublicBusinessType(BaseModel):
    id: str
    world_id: str
    type_key: str
    name: str
    category: str
    open_fee_sat: int = 500
    base_unit_cost_sat: int = 100
    fixed_rent_sat: int = 10
    base_capacity_units: int = 20


############################ Agents ############################
class Agent(BaseModel):
    id: str
    world_id: str
    display_name: str
    api_key_hash: str
    payout_lnaddress: str | None = None
    status: str = "active"
    last_claimed_at: datetime | None = None
    last_opened_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SafeAgent(BaseModel):
    id: str
    world_id: str
    display_name: str
    payout_lnaddress: str | None = None
    status: str = "active"
    last_claimed_at: datetime | None = None
    last_opened_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UpdateAgent(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    payout_lnaddress: str | None = Field(default=None, max_length=254)
    status: Literal["active", "inactive"] | None = None


############################ Businesses ############################
class Business(BaseModel):
    id: str
    world_id: str
    agent_id: str
    business_type_id: str
    district_id: str
    display_name: str
    status: str = "active"
    cash_sat: int = 0
    reputation: float = 0.5
    reliability: float = 0.7
    quality_level: float = 0.5
    price_sat: int = 100
    stock_units: int = 0
    missed_epochs: int = 0
    distress_epochs: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None


class UpdateBusiness(BaseModel):
    status: Literal["active", "distress", "closed"] | None = None
    price_sat: int | None = Field(default=None, ge=1)
    stock_units: int | None = Field(default=None, ge=0)
    cash_sat: int | None = None
    reputation: float | None = None
    reliability: float | None = None
    quality_level: float | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=80)


class BusinessBoardItem(BaseModel):
    business_id: str
    agent_id: str
    display_name: str
    district_id: str
    district_name: str
    business_type_name: str
    status: str
    cash_sat: int
    reputation: float
    reliability: float
    quality_level: float
    price_sat: int
    stock_units: int
    latest_profit_sat: int = 0
    latest_revenue_sat: int = 0
    latest_units_sold: int = 0
    cash_delta_sat: int = 0
    cash_delta_percent: float | None = None
    latest_snapshot_epoch: int | None = None


############################ Epochs ############################
class Epoch(BaseModel):
    id: str
    world_id: str
    epoch_number: int
    season_number: int
    started_at: datetime
    submission_deadline_at: datetime
    digest_at: datetime
    resolved_at: datetime | None = None
    status: str = "open"
    event_summary_text: str | None = None
    digest_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


############################ Submissions ############################
class Submission(BaseModel):
    id: str
    world_id: str
    epoch_number: int
    business_id: str
    payload_text: str
    is_valid: bool = True
    validation_error: str | None = None
    submitted_at: datetime = Field(default_factory=utc_now)


class SubmissionView(BaseModel):
    id: str
    world_id: str
    epoch_number: int
    business_id: str
    payload: ActionPayload
    is_valid: bool = True
    validation_error: str | None = None
    submitted_at: datetime = Field(default_factory=utc_now)


class SubmissionAccepted(BaseModel):
    submission_id: str
    world_id: str
    epoch_number: int
    business_id: str
    accepted: bool
    replaced_previous: bool = False
    validation_error: str | None = None
    submitted_at: datetime = Field(default_factory=utc_now)


############################ Snapshots ############################
class BusinessEpochSnapshot(BaseModel):
    id: str
    world_id: str
    epoch_number: int
    business_id: str
    units_sold: int = 0
    revenue_sat: int = 0
    profit_sat: int = 0
    stock_before: int = 0
    stock_after: int = 0
    cash_before: int = 0
    cash_after: int = 0
    reputation_before: float = 0
    reputation_after: float = 0
    reliability_before: float = 0
    reliability_after: float = 0
    quality_before: float = 0
    quality_after: float = 0
    created_at: datetime = Field(default_factory=utc_now)


############################ Seasons ############################
class SeasonResult(BaseModel):
    id: str
    world_id: str
    season_number: int
    epoch_start: int
    epoch_end: int
    leaderboard_text: str
    payout_status: str = "pending"
    payout_summary_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


############################ Payment Requests ############################
class ClaimBusinessRequest(BaseModel):
    world_id: str | None = None
    display_name: str = Field(min_length=1, max_length=80)
    district_id: str = Field(min_length=1, max_length=128)
    business_type_id: str = Field(min_length=1, max_length=128)
    payout_lnaddress: str = Field(min_length=3, max_length=254)

    class Config:
        extra = "forbid"


class PaymentRequestRecord(BaseModel):
    id: str
    world_id: str
    district_id: str
    business_type_id: str
    display_name: str
    payout_lnaddress: str
    payment_hash: str
    payment_request: str | None = None
    amount_sat: int
    operations_amount_sat: int = 0
    prize_pool_amount_sat: int = 0
    lnbits_tribute_amount_sat: int = 0
    status: str = "pending"
    reservation_expires_at: datetime | None = None
    claim_token: str
    agent_id: str | None = None
    business_id: str | None = None
    issued_api_key: str | None = None
    credentials_revealed: bool = False
    paid_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PaymentRequestResponse(BaseModel):
    payment_request_id: str
    payment_hash: str
    payment_request: str
    amount_sat: int
    claim_token: str


class PaymentStatusResponse(BaseModel):
    payment_request_id: str
    payment_hash: str
    status: str
    paid_at: datetime | None = None


class AgentCredentialReveal(BaseModel):
    agent_id: str
    business_id: str
    api_key: str
    display_name: str
    payment_status: str


############################ Audit ############################
class AuditEvent(BaseModel):
    id: str
    world_id: str
    event_type: str
    entity_id: str | None = None
    payload_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


############################ Public / Agent Responses ############################
class PublicWorldState(BaseModel):
    world: PublicWorld
    current_epoch: Epoch | None = None
    districts: list[PublicDistrict] = Field(default_factory=list)
    business_types: list[PublicBusinessType] = Field(default_factory=list)
    businesses: list[BusinessBoardItem] = Field(default_factory=list)
    leaderboard: list[LeaderboardEntry] = Field(default_factory=list)
    recent_digests: list[EpochDigest] = Field(default_factory=list)


class AgentSession(BaseModel):
    agent: SafeAgent
    business: Business
    current_epoch: Epoch
    latest_submission: SubmissionView | None = None
    recent_snapshots: list[BusinessEpochSnapshot] = Field(default_factory=list)


class AdminDashboard(BaseModel):
    world: AdminWorld
    current_epoch: Epoch | None = None
    districts: list[PublicDistrict] = Field(default_factory=list)
    business_types: list[BusinessType] = Field(default_factory=list)
    agents: list[SafeAgent] = Field(default_factory=list)
    businesses: list[BusinessBoardItem] = Field(default_factory=list)
    epochs: list[Epoch] = Field(default_factory=list)
    submissions: list[SubmissionView] = Field(default_factory=list)
    season_results: list[SeasonResult] = Field(default_factory=list)
    pending_payments: list[PaymentStatusResponse] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class AdminEvent(BaseModel):
    scope: str
    event: str
    entity_id: str | None = None
    world_id: str | None = None


class PublicWorldEvent(BaseModel):
    world_id: str
    event: str
    epoch_number: int | None = None
    payment_request_id: str | None = None
    payment_hash: str | None = None
