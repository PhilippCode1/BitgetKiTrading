"""
Zahlungs-, Abo-, Vertrags- und Gewinnbeteiligungskonstanten (Modul Mate GmbH).

Bezug: docs/BILLING_CONTRACT_PROFITSHARE_MODUL_MATE.md (Prompt 8).

Preise in EUR-Cent (netto/brutto-Uebersicht ueber commercial_data_model.vat_amounts_from_net_cents).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Final

from shared_py.commercial_data_model import DE_VAT_RATE_STANDARD, vat_amounts_from_net_cents
from shared_py.customer_lifecycle import LifecyclePhase
from shared_py.customer_portal_contract import SubscriptionIntervalId

BILLING_SUBSCRIPTION_CONTRACT_VERSION = "1.1.0"
BILLING_SUBSCRIPTION_DOCUMENT_ID = "BILLING_CONTRACT_PROFITSHARE_MODUL_MATE"

# [FEST Prompt 8] Referenz-Tagespreis netto
STANDARD_DAILY_NET_CENTS_EUR: Final[int] = 1_000

# [FEST Prompt 8] Regel-USt (Deckungsgleich mit commercial_data_model)
STANDARD_VAT_RATE: Final[Decimal] = DE_VAT_RATE_STANDARD

# [FEST Prompt 8] Gewinnbeteiligung 10 % = 1000 Basispunkte
DEFAULT_PROFIT_SHARE_BASIS_POINTS: Final[int] = 1_000


class PaymentRailId(str, Enum):
    """
    Internationale Zahlarten / Rails [ANNAHME: fachlich gewuenscht, PSP-Integration folgt].

    Nicht jede Methode ist in jedem Land oder fuer jedes Produkt zulaessig — siehe Compliance-Tags.
    """

    PAYPAL = "paypal"
    ALIPAY = "alipay"
    WISE = "wise"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    CARD_SCHEME = "card_scheme"
    SEPA_DEBIT = "sepa_debit"
    OTHER = "other"


class DunningStage(str, Enum):
    """Mahn- und Sperrlogik nach Zahlungsausfall [ANNAHME]."""

    NONE = "none"
    REMINDER_SOFT = "reminder_soft"
    REMINDER_FIRM = "reminder_firm"
    SERVICE_SUSPENDED = "service_suspended"
    SUBSCRIPTION_TERMINATED = "subscription_terminated"


class BillingComplianceReviewTag(str, Enum):
    """Extern zu pruefen: Steuer, PSP, Vertrag, Regulierung."""

    VAT_RATE_AND_PLACE_OF_SUPPLY = "vat_rate_and_place_of_supply"
    B2B_REVERSE_CHARGE_EU = "b2b_reverse_charge_eu"
    PSP_CONTRACT_AND_PCI_SCOPE = "psp_contract_and_pci_scope"
    PAYMENT_METHOD_PER_COUNTRY = "payment_method_per_country"
    PROFIT_SHARE_LEGAL_CHARACTERIZATION = "profit_share_legal_characterization"
    INVOICE_CONTENT_COMMERCIAL_LAW = "invoice_content_commercial_law"
    CONSUMER_WITHDRAWAL_AND_TERMS = "consumer_withdrawal_and_terms"
    REGULATORY_PRODUCT_CLASSIFICATION = "regulatory_product_classification"


@dataclass(frozen=True)
class SubscriptionPlanTemplate:
    """Referenz-Abo: ein Intervall, Netto in Cent fuer die Periode, optional Kurzname."""

    interval: SubscriptionIntervalId
    net_cents_per_period: int
    code: str
    display_name_de: str


def _week_net_cents() -> int:
    return 7 * STANDARD_DAILY_NET_CENTS_EUR


def _month_net_cents() -> int:
    # [ANNAHME] 30-Tage-Aequivalent
    return 30 * STANDARD_DAILY_NET_CENTS_EUR


def _year_net_cents() -> int:
    # [ANNAHME] 365-Tage-Richtwert
    return 365 * STANDARD_DAILY_NET_CENTS_EUR


STANDARD_SUBSCRIPTION_PLAN_TEMPLATES: Final[tuple[SubscriptionPlanTemplate, ...]] = (
    SubscriptionPlanTemplate(
        SubscriptionIntervalId.DAY,
        STANDARD_DAILY_NET_CENTS_EUR,
        "sub_daily_std",
        "Tagesabo",
    ),
    SubscriptionPlanTemplate(
        SubscriptionIntervalId.WEEK,
        _week_net_cents(),
        "sub_week_std",
        "Wochenabo",
    ),
    SubscriptionPlanTemplate(
        SubscriptionIntervalId.MONTH,
        _month_net_cents(),
        "sub_month_std",
        "Monatsabo",
    ),
    SubscriptionPlanTemplate(
        SubscriptionIntervalId.YEAR,
        _year_net_cents(),
        "sub_year_std",
        "Jahresabo",
    ),
)


def plan_template_by_code(code: str) -> SubscriptionPlanTemplate | None:
    for p in STANDARD_SUBSCRIPTION_PLAN_TEMPLATES:
        if p.code == code:
            return p
    return None


def subscription_list_gross_preview_de() -> list[dict[str, int | str]]:
    """
    Referenzliste Netto/USt/Brutto je Standardplan — fuer UI/Admin-Preview.

    Alle Betraege EUR-Cent.
    """
    out: list[dict[str, int | str]] = []
    for tpl in STANDARD_SUBSCRIPTION_PLAN_TEMPLATES:
        v = vat_amounts_from_net_cents(tpl.net_cents_per_period, STANDARD_VAT_RATE)
        out.append(
            {
                "code": tpl.code,
                "name_de": tpl.display_name_de,
                "interval": tpl.interval.value,
                "net_cents": v["net_cents"],
                "vat_cents": v["vat_cents"],
                "gross_cents": v["gross_cents"],
            }
        )
    return out


def requires_contract_acceptance_to_proceed_to_paid_live(phase: LifecyclePhase) -> bool:
    """
    [FEST] Nach der Probephase ist eine angenommene Vereinbarung Voraussetzung fuer
    die Kette Richtung bezahltem Abo und Echtgeld.

    True, solange der Kunde ausserhalb der reinen Test-/Onboarding-Phasen ist und
    noch keine wirksame Vereinbarung hat.
    """
    if contract_accepted_for_billing(phase):
        return False
    if phase in (
        LifecyclePhase.PROSPECT,
        LifecyclePhase.REGISTERED,
        LifecyclePhase.EMAIL_VERIFIED,
        LifecyclePhase.TRIAL_ACTIVE,
    ):
        return False
    return True


def contract_accepted_for_billing(phase: LifecyclePhase) -> bool:
    """True, wenn Vereinbarung wirksam angenommen (Abo/Zahlungspfad)."""
    return phase in (
        LifecyclePhase.CONTRACT_ACTIVE,
        LifecyclePhase.PAYMENT_PENDING,
        LifecyclePhase.PAYMENT_ACTIVE,
        LifecyclePhase.LIVE_PREPARED,
        LifecyclePhase.LIVE_RELEASED,
    )


def profit_share_fee_cents_default(profit_basis_cents: int) -> int:
    """10 %-Anteil auf die Basis in Cent (Rundung wie commercial_data_model)."""
    from shared_py.commercial_data_model import profit_share_fee_cents

    return profit_share_fee_cents(profit_basis_cents, DEFAULT_PROFIT_SHARE_BASIS_POINTS)


def billing_subscription_descriptor() -> dict[str, str | int]:
    return {
        "billing_subscription_contract_version": BILLING_SUBSCRIPTION_CONTRACT_VERSION,
        "billing_subscription_document_id": BILLING_SUBSCRIPTION_DOCUMENT_ID,
        "standard_daily_net_cents_eur": STANDARD_DAILY_NET_CENTS_EUR,
        "default_profit_share_basis_points": DEFAULT_PROFIT_SHARE_BASIS_POINTS,
        "standard_plan_count": len(STANDARD_SUBSCRIPTION_PLAN_TEMPLATES),
        "payment_rail_count": len(PaymentRailId),
        "prompt13_db_migration": "609_subscription_billing_ledger",
        "standard_vat_rate_percent": int(STANDARD_VAT_RATE * 100),
    }
