"""
Fachliches Datenmodell (Modul Mate GmbH) — logische Kontrakte und Steuer-Helfer.

Bezug: docs/DATA_MODEL_MODUL_MATE.md (Prompt 4).

Enthaelt keine ORM-Mapper; Services speichern Felder in Postgres o. ae.
Secrets erscheinen nur als Verweise (secret_store_key), nie als Klartext.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

COMMERCIAL_DATA_MODEL_VERSION = "1.0.0"
DATA_MODEL_DOCUMENT_ID = "DATA_MODEL_MODUL_MATE"

# Regel-USt Deutschland (Standardsteuersatz) — [ANNAHME] bis steuerliche Festlegung
DE_VAT_RATE_STANDARD: Decimal = Decimal("0.19")


class TaxCustomerType(str, Enum):
    B2C_DE = "b2c_de"
    B2B_DE = "b2b_de"
    B2B_EU = "b2b_eu"
    OTHER = "other"


class TrialPeriodStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"
    EXTENDED = "extended"


class ContractStatus(str, Enum):
    NONE = "none"
    OFFERED = "offered"
    PENDING_ACCEPTANCE = "pending_acceptance"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    TERMINATED = "terminated"


class SubscriptionStatus(str, Enum):
    NONE = "none"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class InvoiceLineType(str, Enum):
    SUBSCRIPTION = "subscription"
    PERFORMANCE_FEE = "performance_fee"
    ADJUSTMENT = "adjustment"
    OTHER = "other"


class PaymentEventType(str, Enum):
    AUTHORIZATION = "authorization"
    CAPTURE = "capture"
    FAILED = "failed"
    REFUND = "refund"
    CHARGEBACK = "chargeback"


class DocumentType(str, Enum):
    CONTRACT_PDF = "contract_pdf"
    INVOICE_PDF = "invoice_pdf"
    CONSENT = "consent"
    OTHER = "other"


class WalletKind(str, Enum):
    DEMO = "demo"
    LIVE = "live"


class ExchangeConnectionMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class ExchangeConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"
    REVOKED = "revoked"


class TelegramLinkStatus(str, Enum):
    PENDING = "pending"
    LINKED = "linked"
    REVOKED = "revoked"


class OrderWalletKind(str, Enum):
    DEMO = "demo"
    LIVE = "live"


class OrderStatus(str, Enum):
    NEW = "new"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    ERROR = "error"


class OrderSource(str, Enum):
    USER = "user"
    KI_SUGGESTION = "ki_suggestion"
    TELEGRAM = "telegram"


class PerformancePeriodStatus(str, Enum):
    OPEN = "open"
    LOCKED = "locked"
    ACCRUED = "accrued"
    INVOICED = "invoiced"
    SETTLED = "settled"


class ProfitShareBasis(str, Enum):
    NET_PROFIT_AFTER_FEES = "net_profit_after_fees"
    HIGH_WATER_MARK = "high_water_mark"


class ApprovalType(str, Enum):
    LIVE_TRADING = "live_trading"
    API_TRADING = "api_trading"
    TELEGRAM_LIVE = "telegram_live"
    CONTRACT_ACCEPTANCE = "contract_acceptance"
    MANUAL_OVERRIDE = "manual_override"


class ApprovalDecision(str, Enum):
    GRANTED = "granted"
    REVOKED = "revoked"


class RestrictionKind(str, Enum):
    PAUSE = "pause"
    SUSPEND = "suspend"
    COMPLIANCE_HOLD = "compliance_hold"


class RestrictionScope(str, Enum):
    ALL = "all"
    LIVE_ONLY = "live_only"
    TELEGRAM = "telegram"
    API = "api"


def vat_amounts_from_net_cents(
    net_cents: int,
    vat_rate: Decimal = DE_VAT_RATE_STANDARD,
) -> dict[str, int]:
    """
    Berechnet USt und Brutto aus Netto (alle Betraege in Cent, ganzzahlig).

    Rundung: Halbauf auf ganze Cent auf der USt-Komponente.
    """
    if net_cents < 0:
        raise ValueError("net_cents must be non-negative")
    d_net = Decimal(net_cents)
    d_vat = (d_net * vat_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    vat_cents = int(d_vat)
    return {
        "net_cents": net_cents,
        "vat_cents": vat_cents,
        "gross_cents": net_cents + vat_cents,
    }


def net_profit_after_fees_cents(realized_pnl_cents: int, fees_cents: int) -> int:
    """Gewinnbasis nach Gebuehren (Vereinfachung; Details im Vertrag)."""
    return realized_pnl_cents - fees_cents


def profit_share_fee_cents(profit_basis_cents: int, rate_basis_points: int) -> int:
    """
    Gewinnbeteiligung in Cent. rate_basis_points: 10000 = 100 %, 2000 = 20 %.
    """
    if profit_basis_cents < 0 or rate_basis_points < 0:
        raise ValueError("profit_basis_cents and rate_basis_points must be non-negative")
    raw = Decimal(profit_basis_cents) * Decimal(rate_basis_points) / Decimal(10000)
    return int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def invoice_lines_net_vat_gross_totals(lines: list[dict[str, Any]]) -> dict[str, int]:
    """
    Summiert Rechnungspositionen mit Feldern net_cents, vat_cents, gross_cents.

    Raises:
        KeyError: wenn Pflichtfelder fehlen.
    """
    total_net = total_vat = total_gross = 0
    for row in lines:
        total_net += int(row["net_cents"])
        total_vat += int(row["vat_cents"])
        total_gross += int(row["gross_cents"])
    return {"net_cents": total_net, "vat_cents": total_vat, "gross_cents": total_gross}


def invoice_may_be_mutated(status: InvoiceStatus) -> bool:
    """Nach Ausstellung fachlich nicht mehr aendern ([ANNAHME] Storno ueber neue Belege)."""
    return status == InvoiceStatus.DRAFT


class OrganizationRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    legal_name: str = Field(min_length=1)
    vat_id: str | None = None
    invoice_prefix: str = Field(default="MM", min_length=1)
    default_currency: str = Field(default="EUR", min_length=3, max_length=3)


class CustomerAccountRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    customer_number: str = Field(min_length=1, description="Menschenlesbare Kundennummer")


class TrialPeriodRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    started_at: datetime
    ends_at: datetime
    status: TrialPeriodStatus
    source: str = Field(default="user_started", description="user_started | auto")


class ContractVersionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    code: str = Field(min_length=1, description="z. B. AGB_2026_04")
    title: str = Field(min_length=1)
    effective_from: datetime
    content_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class ContractRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    contract_version_id: str = Field(min_length=1)
    status: ContractStatus
    accepted_at: datetime | None = None
    document_id: str | None = None


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    owner_type: str = Field(description="customer | org")
    owner_id: str = Field(min_length=1)
    doc_type: DocumentType
    storage_key: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    mime: str = Field(default="application/pdf")
    size_bytes: int = Field(default=0, ge=0)


class SubscriptionPlanRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    interval: str = Field(description="month | year")
    gross_amount_cents: int = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    vat_rate: Decimal = Field(default=DE_VAT_RATE_STANDARD)
    active: bool = True


class SubscriptionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    status: SubscriptionStatus
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    external_provider: str | None = None
    external_subscription_id: str | None = None


class TaxProfileRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    customer_account_id: str = Field(min_length=1)
    customer_type: TaxCustomerType
    vat_id: str | None = None
    tax_exempt: bool = False


class InvoiceLineRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    invoice_id: str = Field(min_length=1)
    line_type: InvoiceLineType
    description: str = Field(min_length=1)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_net_cents: int = Field(ge=0)
    net_cents: int = Field(ge=0)
    vat_rate: Decimal = Field(default=DE_VAT_RATE_STANDARD)
    vat_cents: int = Field(ge=0)
    gross_cents: int = Field(ge=0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class InvoiceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    organization_id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    invoice_number: str = Field(min_length=1)
    issued_at: datetime | None = None
    due_at: datetime | None = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    subtotal_net_cents: int = Field(ge=0)
    vat_rate: Decimal = Field(default=DE_VAT_RATE_STANDARD, description="Anzeige; Zeilen koennen abweichen")
    vat_amount_cents: int = Field(ge=0)
    total_gross_cents: int = Field(ge=0)
    status: InvoiceStatus = InvoiceStatus.DRAFT
    subscription_id: str | None = None
    performance_period_id: str | None = None
    pdf_document_id: str | None = None


class PaymentMethodRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    provider_pm_id: str = Field(min_length=1)
    brand: str | None = None
    last4: str | None = Field(default=None, min_length=4, max_length=4)
    status: str = Field(default="active")


class PaymentEventRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    invoice_id: str | None = None
    provider: str = Field(min_length=1)
    provider_event_id: str = Field(min_length=1)
    type: PaymentEventType
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    occurred_at: datetime
    status: str = Field(default="posted")


class WalletAccountRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    kind: WalletKind
    base_currency: str = Field(default="EUR", min_length=3, max_length=3)


class ApiCredentialRefRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    exchange_connection_id: str = Field(min_length=1)
    secret_store_key: str = Field(min_length=1)
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None


class ExchangeConnectionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    exchange: str = Field(min_length=1, description="bitget | ...")
    mode: ExchangeConnectionMode
    status: ExchangeConnectionStatus
    api_credential_ref_id: str | None = None
    wallet_account_id: str | None = None


class TelegramLinkRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    telegram_user_id: str = Field(min_length=1)
    chat_id: str = Field(min_length=1)
    status: TelegramLinkStatus
    linked_at: datetime | None = None
    allows_live_actions: bool = False


class OrderRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    wallet_kind: OrderWalletKind
    client_order_id: str = Field(min_length=1)
    exchange_order_id: str | None = None
    symbol: str = Field(min_length=1)
    side: str = Field(min_length=1)
    type: str = Field(min_length=1)
    status: OrderStatus
    trace_id: str | None = None
    source: OrderSource = OrderSource.USER
    exchange_connection_id: str | None = None


class TradeFillRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    fill_id_exchange: str = Field(min_length=1)
    qty: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    fee: Decimal = Field(default=Decimal("0"))
    fee_asset: str | None = None
    occurred_at: datetime


class PerformancePeriodRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    starts_at: datetime
    ends_at: datetime
    status: PerformancePeriodStatus


class ProfitShareRuleRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str | None = None
    active_from: datetime
    active_to: datetime | None = None
    basis: ProfitShareBasis
    rate_basis_points: int = Field(ge=0, le=10000)
    cap_cents: int | None = Field(default=None, ge=0)
    floor_cents: int | None = Field(default=None, ge=0)


class ProfitShareAccrualRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    performance_period_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    basis_amount_cents: int
    fee_amount_cents: int = Field(ge=0)
    calculation_json: dict[str, Any] = Field(default_factory=dict)
    finalized_at: datetime | None = None


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    approval_type: ApprovalType
    decision: ApprovalDecision
    decided_at: datetime
    decided_by_user_id: str = Field(min_length=1)
    note: str = Field(min_length=1)


class RestrictionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    kind: RestrictionKind
    scope: RestrictionScope
    starts_at: datetime
    ends_at: datetime | None = None
    reason_code: str = Field(min_length=1)
    created_by_user_id: str | None = None


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    occurred_at: datetime
    actor_user_id: str | None = None
    actor_role: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    before_json: dict[str, Any] = Field(default_factory=dict)
    after_json: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class SupportNoteRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    customer_account_id: str = Field(min_length=1)
    author_user_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    visibility: str = Field(default="admin_only", description="admin_only | support")
    pinned: bool = False
    created_at: datetime


def commercial_data_model_descriptor() -> dict[str, str | int]:
    return {
        "commercial_data_model_version": COMMERCIAL_DATA_MODEL_VERSION,
        "data_model_document_id": DATA_MODEL_DOCUMENT_ID,
        "de_vat_rate_standard": str(DE_VAT_RATE_STANDARD),
    }
