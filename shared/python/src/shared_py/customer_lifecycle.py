"""
Rollen, Kunden-Lebenszyklus und Nutzerwege (Modul Mate GmbH).

Bezug: docs/ROLES_AND_LIFECYCLE_MODUL_MATE.md (Prompt 2).

Persistenz (DB-Felder) liegt in den Services; dieses Modul liefert kanonische Enums,
erlaubte Phasenuebergaenge, Kundenfaehigkeiten und die Abbildung auf product_policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared_py.product_policy import (
    TRIAL_PERIOD_DAYS,
    CustomerCommercialGates,
    demo_trading_allowed,
    exchange_api_connection_allowed,
    live_trading_allowed,
    trial_period_days,
)

CUSTOMER_LIFECYCLE_MODULE_VERSION = "1.1.1"
ROLES_DOCUMENT_ID = "ROLES_AND_LIFECYCLE_MODUL_MATE"


class PlatformRole(str, Enum):
    """
    Plattform-Rolle (AuthZ). Super-Admin ist [FEST] Philipp Crljic.

    JWT-Portal-Spiegelung: `shared_py.portal_access_contract` (portal_roles / platform_role).
    """

    CUSTOMER = "customer"
    SUPER_ADMIN = "super_admin"
    SUPPORT_READ = "support_read"


class LifecyclePhase(str, Enum):
    """
    Basis-Lebenszyklus eines Kundenkontos (ohne Pause/Sperre-Overlay).

    PROSPECT = noch kein Konto; typischerweise kein DB-User.
    """

    PROSPECT = "prospect"
    REGISTERED = "registered"
    EMAIL_VERIFIED = "email_verified"
    TRIAL_ACTIVE = "trial_active"
    TRIAL_ENDED = "trial_ended"
    CONTRACT_PENDING = "contract_pending"
    CONTRACT_ACTIVE = "contract_active"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_ACTIVE = "payment_active"
    LIVE_PREPARED = "live_prepared"
    LIVE_RELEASED = "live_released"


class TransitionActor(str, Enum):
    """Wer den Statuswechsel ausloesen darf."""

    SYSTEM = "system"
    USER = "user"
    ADMIN = "admin"


class CustomerLifecycleStatus(str, Enum):
    """
    Oeffentliche Statusmaschine (Prompt 11).

    Ergaenzt das feinere interne `LifecyclePhase`-Modell; Persistenz und API
    nutzen diese kanonischen Strings.
    """

    INVITED = "invited"
    REGISTERED = "registered"
    TRIAL_ACTIVE = "trial_active"
    TRIAL_EXPIRED = "trial_expired"
    CONTRACT_PENDING = "contract_pending"
    CONTRACT_SIGNED_WAITING_ADMIN = "contract_signed_waiting_admin"
    LIVE_APPROVED = "live_approved"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CustomerLifecycleSnapshot:
    """Abbild eines Kundenlebenszyklus fuer Policy-Auswertung."""

    phase: LifecyclePhase
    is_paused: bool = False
    is_suspended: bool = False
    is_cancelled: bool = False


# (from_phase, to_phase, erlaubte Akteure)
ALLOWED_LIFECYCLE_TRANSITIONS: tuple[tuple[LifecyclePhase, LifecyclePhase, frozenset[TransitionActor]], ...] = (
    (LifecyclePhase.REGISTERED, LifecyclePhase.EMAIL_VERIFIED, frozenset({TransitionActor.SYSTEM})),
    (LifecyclePhase.EMAIL_VERIFIED, LifecyclePhase.TRIAL_ACTIVE, frozenset({TransitionActor.USER})),
    (LifecyclePhase.TRIAL_ACTIVE, LifecyclePhase.TRIAL_ENDED, frozenset({TransitionActor.SYSTEM})),
    (LifecyclePhase.TRIAL_ACTIVE, LifecyclePhase.CONTRACT_PENDING, frozenset({TransitionActor.USER})),
    (LifecyclePhase.TRIAL_ENDED, LifecyclePhase.CONTRACT_PENDING, frozenset({TransitionActor.SYSTEM, TransitionActor.USER})),
    (LifecyclePhase.CONTRACT_PENDING, LifecyclePhase.CONTRACT_ACTIVE, frozenset({TransitionActor.USER})),
    (LifecyclePhase.CONTRACT_ACTIVE, LifecyclePhase.PAYMENT_PENDING, frozenset({TransitionActor.SYSTEM})),
    (LifecyclePhase.PAYMENT_PENDING, LifecyclePhase.PAYMENT_ACTIVE, frozenset({TransitionActor.SYSTEM})),
    (LifecyclePhase.PAYMENT_ACTIVE, LifecyclePhase.LIVE_PREPARED, frozenset({TransitionActor.SYSTEM, TransitionActor.USER})),
    (LifecyclePhase.LIVE_PREPARED, LifecyclePhase.LIVE_RELEASED, frozenset({TransitionActor.ADMIN})),
    (LifecyclePhase.LIVE_RELEASED, LifecyclePhase.LIVE_PREPARED, frozenset({TransitionActor.ADMIN})),
)


def is_lifecycle_transition_allowed(
    from_phase: LifecyclePhase,
    to_phase: LifecyclePhase,
    actor: TransitionActor,
) -> bool:
    """True, wenn der Wechsel laut definierter Statusmaschine erlaubt ist."""
    if from_phase == to_phase:
        return True
    for f, t, actors in ALLOWED_LIFECYCLE_TRANSITIONS:
        if f == from_phase and t == to_phase and actor in actors:
            return True
    return False


def allowed_lifecycle_targets(
    from_phase: LifecyclePhase,
    actor: TransitionActor,
) -> frozenset[LifecyclePhase]:
    """Alle Zielphasen, die von from_phase mit diesem Akteur erreichbar sind."""
    out: set[LifecyclePhase] = {from_phase}
    for f, t, actors in ALLOWED_LIFECYCLE_TRANSITIONS:
        if f == from_phase and actor in actors:
            out.add(t)
    return frozenset(out)


def commercial_gates_from_lifecycle(snapshot: CustomerLifecycleSnapshot) -> CustomerCommercialGates:
    """
    Mappt den Lebenszyklus auf die booleschen Gates aus product_policy.

    Semantik [ANNAHME]:
    - trial_active nur in TRIAL_ACTIVE.
    - contract_accepted ab CONTRACT_ACTIVE (inkl. nachgelagerter Phasen).
    - subscription_active ab PAYMENT_ACTIVE (Abo in Ordnung).
    - admin_live_trading_granted nur in LIVE_RELEASED.
    """
    if snapshot.is_cancelled:
        return CustomerCommercialGates(
            trial_active=False,
            contract_accepted=False,
            admin_live_trading_granted=False,
            subscription_active=False,
            account_paused=False,
            account_suspended=False,
        )
    p = snapshot.phase
    trial_active = p == LifecyclePhase.TRIAL_ACTIVE
    contract_accepted = p in (
        LifecyclePhase.CONTRACT_ACTIVE,
        LifecyclePhase.PAYMENT_PENDING,
        LifecyclePhase.PAYMENT_ACTIVE,
        LifecyclePhase.LIVE_PREPARED,
        LifecyclePhase.LIVE_RELEASED,
    )
    subscription_active = p in (
        LifecyclePhase.PAYMENT_ACTIVE,
        LifecyclePhase.LIVE_PREPARED,
        LifecyclePhase.LIVE_RELEASED,
    )
    admin_live_trading_granted = p == LifecyclePhase.LIVE_RELEASED
    return CustomerCommercialGates(
        trial_active=trial_active,
        contract_accepted=contract_accepted,
        admin_live_trading_granted=admin_live_trading_granted,
        subscription_active=subscription_active,
        account_paused=snapshot.is_paused,
        account_suspended=snapshot.is_suspended,
    )


@dataclass(frozen=True)
class CustomerCapabilities:
    """
    Was ein Kunde in der Oberflaeche / API tun darf (grobe Matrix).

    Feingranulare Pruefungen (2FA, OTP, Boersen-Health) bleiben in den Services.
    """

    browse_marketing: bool
    register_and_login: bool
    verify_email: bool
    start_trial: bool
    view_dashboard: bool
    demo_trading: bool
    view_contract_offer: bool
    accept_contract: bool
    manage_subscription_payment: bool
    connect_exchange_for_health_check: bool
    store_live_exchange_credentials: bool
    execute_live_orders: bool
    telegram_info_messages: bool
    telegram_live_actions: bool
    access_support_area: bool


def derive_customer_capabilities(snapshot: CustomerLifecycleSnapshot) -> CustomerCapabilities:
    """
    Faehigkeiten aus Phase + Overlay.

    [ANNAHME] Telegram Live nur wenn execute_live_orders; OTP in Services.
    Live-API-Credentials speicherbar erst ab aktiver Vereinbarung (keine Live-Keys vor Vertrag).
    """
    if snapshot.is_cancelled:
        return CustomerCapabilities(
            browse_marketing=False,
            register_and_login=False,
            verify_email=False,
            start_trial=False,
            view_dashboard=False,
            demo_trading=False,
            view_contract_offer=False,
            accept_contract=False,
            manage_subscription_payment=False,
            connect_exchange_for_health_check=False,
            store_live_exchange_credentials=False,
            execute_live_orders=False,
            telegram_info_messages=False,
            telegram_live_actions=False,
            access_support_area=False,
        )
    p = snapshot.phase
    blocked = snapshot.is_suspended or snapshot.is_paused
    gates = commercial_gates_from_lifecycle(snapshot)

    demo_ok = not blocked and demo_trading_allowed(gates)
    live_ok = not blocked and live_trading_allowed(gates)
    health_ok, _ = exchange_api_connection_allowed(gates, purpose="read_only_health")

    store_creds = (
        not blocked
        and p
        in (
            LifecyclePhase.CONTRACT_ACTIVE,
            LifecyclePhase.PAYMENT_PENDING,
            LifecyclePhase.PAYMENT_ACTIVE,
            LifecyclePhase.LIVE_PREPARED,
            LifecyclePhase.LIVE_RELEASED,
        )
    )

    return CustomerCapabilities(
        browse_marketing=True,
        register_and_login=p == LifecyclePhase.PROSPECT,
        verify_email=p == LifecyclePhase.REGISTERED,
        start_trial=p == LifecyclePhase.EMAIL_VERIFIED,
        view_dashboard=p != LifecyclePhase.PROSPECT,
        demo_trading=demo_ok,
        view_contract_offer=p
        in (
            LifecyclePhase.TRIAL_ACTIVE,
            LifecyclePhase.TRIAL_ENDED,
            LifecyclePhase.CONTRACT_PENDING,
        ),
        accept_contract=p == LifecyclePhase.CONTRACT_PENDING,
        manage_subscription_payment=p
        in (
            LifecyclePhase.CONTRACT_ACTIVE,
            LifecyclePhase.PAYMENT_PENDING,
            LifecyclePhase.PAYMENT_ACTIVE,
            LifecyclePhase.LIVE_PREPARED,
            LifecyclePhase.LIVE_RELEASED,
        ),
        connect_exchange_for_health_check=not snapshot.is_suspended and health_ok,
        store_live_exchange_credentials=store_creds,
        execute_live_orders=live_ok,
        telegram_info_messages=p != LifecyclePhase.PROSPECT and not snapshot.is_suspended,
        telegram_live_actions=live_ok,
        access_support_area=p != LifecyclePhase.PROSPECT,
    )


def customer_journey_title_de(phase: LifecyclePhase) -> str:
    """Kurztitel fuer Kundenoberflaeche (ohne technische Codes)."""
    titles: dict[LifecyclePhase, str] = {
        LifecyclePhase.PROSPECT: "Interessent",
        LifecyclePhase.REGISTERED: "Konto angelegt",
        LifecyclePhase.EMAIL_VERIFIED: "Angemeldet",
        LifecyclePhase.TRIAL_ACTIVE: "Testkunde",
        LifecyclePhase.TRIAL_ENDED: "Probephase beendet",
        LifecyclePhase.CONTRACT_PENDING: "Vereinbarung ausstehend",
        LifecyclePhase.CONTRACT_ACTIVE: "Vereinbarung aktiv",
        LifecyclePhase.PAYMENT_PENDING: "Zahlung ausstehend",
        LifecyclePhase.PAYMENT_ACTIVE: "Abo aktiv",
        LifecyclePhase.LIVE_PREPARED: "Bereit fuer Echtgeld",
        LifecyclePhase.LIVE_RELEASED: "Echtgeld freigegeben",
    }
    return titles[phase]


def platform_role_is_full_admin(role: PlatformRole) -> bool:
    """True fuer alleinigen Voll-Admin ([FEST]: Philipp Crljic als SUPER_ADMIN)."""
    return role == PlatformRole.SUPER_ADMIN


def customer_lifecycle_descriptor() -> dict[str, str | int]:
    return {
        "customer_lifecycle_module_version": CUSTOMER_LIFECYCLE_MODULE_VERSION,
        "roles_document_id": ROLES_DOCUMENT_ID,
        "trial_period_days": trial_period_days(),
        "prompt11_status_machine": True,
    }


# --- Prompt 11: kanonische Statusmaschine + Modul-Mate-Gates ---

_PROMPT11_TRANSITIONS: tuple[
    tuple[CustomerLifecycleStatus, CustomerLifecycleStatus, frozenset[TransitionActor]], ...
] = (
    (CustomerLifecycleStatus.INVITED, CustomerLifecycleStatus.REGISTERED, frozenset({TransitionActor.USER, TransitionActor.SYSTEM})),
    (CustomerLifecycleStatus.REGISTERED, CustomerLifecycleStatus.TRIAL_ACTIVE, frozenset({TransitionActor.USER})),
    (CustomerLifecycleStatus.TRIAL_ACTIVE, CustomerLifecycleStatus.TRIAL_EXPIRED, frozenset({TransitionActor.SYSTEM})),
    (CustomerLifecycleStatus.TRIAL_ACTIVE, CustomerLifecycleStatus.CONTRACT_PENDING, frozenset({TransitionActor.USER})),
    (CustomerLifecycleStatus.TRIAL_EXPIRED, CustomerLifecycleStatus.CONTRACT_PENDING, frozenset({TransitionActor.USER, TransitionActor.SYSTEM})),
    (
        CustomerLifecycleStatus.CONTRACT_PENDING,
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        frozenset({TransitionActor.USER, TransitionActor.SYSTEM}),
    ),
    (
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        CustomerLifecycleStatus.LIVE_APPROVED,
        frozenset({TransitionActor.ADMIN}),
    ),
    (
        CustomerLifecycleStatus.LIVE_APPROVED,
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        frozenset({TransitionActor.ADMIN}),
    ),
    (CustomerLifecycleStatus.INVITED, CustomerLifecycleStatus.CANCELLED, frozenset({TransitionActor.USER, TransitionActor.ADMIN})),
    (CustomerLifecycleStatus.REGISTERED, CustomerLifecycleStatus.CANCELLED, frozenset({TransitionActor.USER, TransitionActor.ADMIN})),
    (CustomerLifecycleStatus.TRIAL_ACTIVE, CustomerLifecycleStatus.CANCELLED, frozenset({TransitionActor.USER, TransitionActor.ADMIN})),
    (CustomerLifecycleStatus.TRIAL_EXPIRED, CustomerLifecycleStatus.CANCELLED, frozenset({TransitionActor.USER, TransitionActor.ADMIN})),
    (CustomerLifecycleStatus.CONTRACT_PENDING, CustomerLifecycleStatus.CANCELLED, frozenset({TransitionActor.USER, TransitionActor.ADMIN})),
    (
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        CustomerLifecycleStatus.CANCELLED,
        frozenset({TransitionActor.USER, TransitionActor.ADMIN}),
    ),
    (CustomerLifecycleStatus.LIVE_APPROVED, CustomerLifecycleStatus.CANCELLED, frozenset({TransitionActor.ADMIN})),
)

_PROMPT11_TO_SUSPENDED: frozenset[CustomerLifecycleStatus] = frozenset(
    {
        CustomerLifecycleStatus.INVITED,
        CustomerLifecycleStatus.REGISTERED,
        CustomerLifecycleStatus.TRIAL_ACTIVE,
        CustomerLifecycleStatus.TRIAL_EXPIRED,
        CustomerLifecycleStatus.CONTRACT_PENDING,
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        CustomerLifecycleStatus.LIVE_APPROVED,
    }
)


def is_prompt11_transition_allowed(
    from_status: CustomerLifecycleStatus,
    to_status: CustomerLifecycleStatus,
    actor: TransitionActor,
    *,
    suspended_previous: CustomerLifecycleStatus | None = None,
) -> bool:
    """Prompt-11-Wechsel inkl. Sperre/Wiederherstellung."""
    if from_status == to_status:
        return True
    if from_status == CustomerLifecycleStatus.SUSPENDED:
        return bool(
            actor == TransitionActor.ADMIN
            and suspended_previous is not None
            and to_status == suspended_previous
        )
    if to_status == CustomerLifecycleStatus.SUSPENDED:
        return actor == TransitionActor.ADMIN and from_status in _PROMPT11_TO_SUSPENDED
    for f, t, actors in _PROMPT11_TRANSITIONS:
        if f == from_status and t == to_status and actor in actors:
            return True
    return False


def allowed_prompt11_targets(
    from_status: CustomerLifecycleStatus,
    actor: TransitionActor,
    *,
    suspended_previous: CustomerLifecycleStatus | None = None,
) -> frozenset[CustomerLifecycleStatus]:
    out: set[CustomerLifecycleStatus] = {from_status}
    if from_status == CustomerLifecycleStatus.SUSPENDED and suspended_previous is not None:
        if is_prompt11_transition_allowed(
            from_status,
            suspended_previous,
            actor,
            suspended_previous=suspended_previous,
        ):
            out.add(suspended_previous)
        return frozenset(out)
    for f, t, actors in _PROMPT11_TRANSITIONS:
        if f == from_status and actor in actors:
            out.add(t)
    if from_status in _PROMPT11_TO_SUSPENDED and actor == TransitionActor.ADMIN:
        out.add(CustomerLifecycleStatus.SUSPENDED)
    return frozenset(out)


def internal_snapshot_from_prompt11(
    status: CustomerLifecycleStatus,
    *,
    email_verified: bool,
) -> CustomerLifecycleSnapshot:
    """
    Abbildung Prompt-11-Status auf internes Phasenmodell fuer Capabilities/Gates.

    CONTRACT_SIGNED_WAITING_ADMIN entspricht LIVE_PREPARED (Zahlung/Abo i. d. R. ok, Admin-Freigabe offen).
    """
    if status == CustomerLifecycleStatus.CANCELLED:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.PROSPECT, is_cancelled=True)
    if status == CustomerLifecycleStatus.SUSPENDED:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.LIVE_PREPARED, is_suspended=True)
    if status == CustomerLifecycleStatus.INVITED:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.PROSPECT)
    if status == CustomerLifecycleStatus.REGISTERED:
        ph = LifecyclePhase.EMAIL_VERIFIED if email_verified else LifecyclePhase.REGISTERED
        return CustomerLifecycleSnapshot(phase=ph)
    if status == CustomerLifecycleStatus.TRIAL_ACTIVE:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.TRIAL_ACTIVE)
    if status == CustomerLifecycleStatus.TRIAL_EXPIRED:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.TRIAL_ENDED)
    if status == CustomerLifecycleStatus.CONTRACT_PENDING:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.CONTRACT_PENDING)
    if status == CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.LIVE_PREPARED)
    if status == CustomerLifecycleStatus.LIVE_APPROVED:
        return CustomerLifecycleSnapshot(phase=LifecyclePhase.LIVE_RELEASED)
    raise ValueError(f"unhandled lifecycle status: {status!r}")


def customer_commercial_gates_for_prompt11(
    status: CustomerLifecycleStatus,
    *,
    trial_clock_active: bool,
) -> CustomerCommercialGates:
    """
    Boolesche Gates fuer `app.tenant_modul_mate_gates` aus Prompt-11-Status.

    trial_clock_active: True bei Status trial_active und now < trial_ends_at (sonst false).
    """
    if status == CustomerLifecycleStatus.CANCELLED:
        return CustomerCommercialGates(
            trial_active=False,
            contract_accepted=False,
            admin_live_trading_granted=False,
            subscription_active=False,
            account_paused=False,
            account_suspended=False,
        )
    if status == CustomerLifecycleStatus.SUSPENDED:
        return CustomerCommercialGates(
            trial_active=False,
            contract_accepted=False,
            admin_live_trading_granted=False,
            subscription_active=False,
            account_paused=False,
            account_suspended=True,
        )
    trial_on = status == CustomerLifecycleStatus.TRIAL_ACTIVE and trial_clock_active
    contract_on = status in (
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        CustomerLifecycleStatus.LIVE_APPROVED,
    )
    sub_on = status in (
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        CustomerLifecycleStatus.LIVE_APPROVED,
    )
    admin_live = status == CustomerLifecycleStatus.LIVE_APPROVED
    return CustomerCommercialGates(
        trial_active=trial_on,
        contract_accepted=contract_on,
        admin_live_trading_granted=admin_live,
        subscription_active=sub_on,
        account_paused=False,
        account_suspended=False,
    )


def derive_capabilities_from_prompt11(
    status: CustomerLifecycleStatus,
    *,
    email_verified: bool,
    trial_clock_active: bool,
) -> CustomerCapabilities:
    """Capabilities unter Beruecksichtigung abgelaufener Trial-Uhr."""
    if status == CustomerLifecycleStatus.TRIAL_ACTIVE and not trial_clock_active:
        snap = internal_snapshot_from_prompt11(
            CustomerLifecycleStatus.TRIAL_EXPIRED,
            email_verified=email_verified,
        )
    else:
        snap = internal_snapshot_from_prompt11(status, email_verified=email_verified)
    return derive_customer_capabilities(snap)


def prompt11_journey_title_de(status: CustomerLifecycleStatus) -> str:
    titles: dict[CustomerLifecycleStatus, str] = {
        CustomerLifecycleStatus.INVITED: "Einladung",
        CustomerLifecycleStatus.REGISTERED: "Registriert",
        CustomerLifecycleStatus.TRIAL_ACTIVE: "Probephase aktiv",
        CustomerLifecycleStatus.TRIAL_EXPIRED: "Probephase beendet",
        CustomerLifecycleStatus.CONTRACT_PENDING: "Vertrag ausstehend",
        CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN: (
            "Vertrag unterschrieben - Admin-Freigabe ausstehend"
        ),
        CustomerLifecycleStatus.LIVE_APPROVED: "Echtgeld freigegeben",
        CustomerLifecycleStatus.SUSPENDED: "Gesperrt",
        CustomerLifecycleStatus.CANCELLED: "Beendet",
    }
    return titles[status]


def lifecycle_phase_to_prompt11(phase: LifecyclePhase) -> CustomerLifecycleStatus:
    """Best-effort Abbildung interner Phase auf Prompt-11 (ohne Sperre/Cancel)."""
    return {
        LifecyclePhase.PROSPECT: CustomerLifecycleStatus.INVITED,
        LifecyclePhase.REGISTERED: CustomerLifecycleStatus.REGISTERED,
        LifecyclePhase.EMAIL_VERIFIED: CustomerLifecycleStatus.REGISTERED,
        LifecyclePhase.TRIAL_ACTIVE: CustomerLifecycleStatus.TRIAL_ACTIVE,
        LifecyclePhase.TRIAL_ENDED: CustomerLifecycleStatus.TRIAL_EXPIRED,
        LifecyclePhase.CONTRACT_PENDING: CustomerLifecycleStatus.CONTRACT_PENDING,
        LifecyclePhase.CONTRACT_ACTIVE: CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        LifecyclePhase.PAYMENT_PENDING: CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        LifecyclePhase.PAYMENT_ACTIVE: CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        LifecyclePhase.LIVE_PREPARED: CustomerLifecycleStatus.CONTRACT_SIGNED_WAITING_ADMIN,
        LifecyclePhase.LIVE_RELEASED: CustomerLifecycleStatus.LIVE_APPROVED,
    }[phase]


def trial_duration_days() -> int:
    """Kalendertage Probephase ([FEST] = TRIAL_PERIOD_DAYS)."""
    return TRIAL_PERIOD_DAYS
