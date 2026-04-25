"""Static secret lifecycle policy for bitget-btc-ai.

The helpers in this module classify secret *names* only. They never accept,
return, log, or derive raw credential values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class SecretPolicy:
    id: str
    owner_role: str
    environments: tuple[str, ...]
    sensitivity: str
    rotation_interval_days: int | None
    expiry_expected: bool
    emergency_revoke_process: str
    where_stored: str
    where_never_stored: str
    production_live_impact: str
    rotation_test_requirement: str


SECRET_POLICIES: dict[str, SecretPolicy] = {
    "BITGET_API_KEY": SecretPolicy(
        id="BITGET_API_KEY",
        owner_role="Trading Operations / Security",
        environments=("shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=30,
        expiry_expected=True,
        emergency_revoke_process="Disable key in Bitget, revoke IP allowlist entry, latch live broker.",
        where_stored="Vault/KMS-backed secret store per environment.",
        where_never_stored="Repo, browser, logs, dashboard payloads, test fixtures.",
        production_live_impact="Live trading must block until replacement key is verified read-only first.",
        rotation_test_requirement="Simulated drill plus demo/read-only exchange verification.",
    ),
    "BITGET_API_SECRET": SecretPolicy(
        id="BITGET_API_SECRET",
        owner_role="Trading Operations / Security",
        environments=("shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=30,
        expiry_expected=True,
        emergency_revoke_process="Revoke exchange credential pair and invalidate dependent broker sessions.",
        where_stored="Vault/KMS-backed secret store per environment.",
        where_never_stored="Repo, browser, logs, dashboard payloads, test fixtures.",
        production_live_impact="Order submission remains blocked until broker health and reconcile are clean.",
        rotation_test_requirement="Simulated drill plus broker restart and reconcile smoke.",
    ),
    "BITGET_API_PASSPHRASE": SecretPolicy(
        id="BITGET_API_PASSPHRASE",
        owner_role="Trading Operations / Security",
        environments=("shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=30,
        expiry_expected=True,
        emergency_revoke_process="Rotate with Bitget keypair and invalidate old passphrase immediately.",
        where_stored="Vault/KMS-backed secret store per environment.",
        where_never_stored="Repo, browser, logs, dashboard payloads, test fixtures.",
        production_live_impact="Live broker must fail closed until full credential set matches.",
        rotation_test_requirement="Simulated drill plus credential-set consistency check.",
    ),
    "OPENAI_API_KEY": SecretPolicy(
        id="OPENAI_API_KEY",
        owner_role="AI Platform / Security",
        environments=("local", "shadow", "production"),
        sensitivity="high",
        rotation_interval_days=60,
        expiry_expected=True,
        emergency_revoke_process="Revoke provider key, pause LLM-dependent workflows, deploy replacement.",
        where_stored="Secret store or local developer vault; never committed.",
        where_never_stored="Repo, browser, logs, prompts, evaluation artifacts.",
        production_live_impact="LLM degradation is allowed; trading execution must not become less safe.",
        rotation_test_requirement="Simulated provider-key rotation and fail-closed LLM fallback test.",
    ),
    "TELEGRAM_BOT_TOKEN": SecretPolicy(
        id="TELEGRAM_BOT_TOKEN",
        owner_role="Operator Communications / Security",
        environments=("shadow", "production"),
        sensitivity="high",
        rotation_interval_days=60,
        expiry_expected=True,
        emergency_revoke_process="Revoke token via Telegram, disable webhook, rotate allowlist.",
        where_stored="Secret store per environment.",
        where_never_stored="Repo, logs, screenshots, browser, chat transcripts.",
        production_live_impact="Operator commands must fail closed until channel is re-verified.",
        rotation_test_requirement="Simulated token rotation and allowlist command test.",
    ),
    "TELEGRAM_WEBHOOK_SECRET": SecretPolicy(
        id="TELEGRAM_WEBHOOK_SECRET",
        owner_role="Operator Communications / Security",
        environments=("shadow", "production"),
        sensitivity="high",
        rotation_interval_days=60,
        expiry_expected=True,
        emergency_revoke_process="Rotate webhook secret and reject old signatures.",
        where_stored="Secret store per environment.",
        where_never_stored="Repo, logs, browser, webhook responses.",
        production_live_impact="Webhook ingestion must reject unsigned or stale requests.",
        rotation_test_requirement="Webhook signature rejection/acceptance test.",
    ),
    "JWT_SECRET": SecretPolicy(
        id="JWT_SECRET",
        owner_role="Platform Security",
        environments=("local", "shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=30,
        expiry_expected=True,
        emergency_revoke_process="Rotate signing key, invalidate sessions, force token renewal.",
        where_stored="Secret store with key version metadata.",
        where_never_stored="Repo, logs, browser storage as raw secret.",
        production_live_impact="Auth must fail closed for tokens signed by revoked keys.",
        rotation_test_requirement="Token invalidation and new-token acceptance test.",
    ),
    "GATEWAY_JWT_SECRET": SecretPolicy(
        id="GATEWAY_JWT_SECRET",
        owner_role="Platform Security",
        environments=("local", "shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=30,
        expiry_expected=True,
        emergency_revoke_process="Rotate gateway signing key and reject old service tokens.",
        where_stored="Secret store with per-environment key version.",
        where_never_stored="Repo, logs, browser storage as raw secret.",
        production_live_impact="Gateway must reject old tokens and surface safe 401/403 responses.",
        rotation_test_requirement="Gateway auth negative/positive rotation test.",
    ),
    "INTERNAL_API_KEY": SecretPolicy(
        id="INTERNAL_API_KEY",
        owner_role="Platform Security",
        environments=("local", "shadow", "production"),
        sensitivity="high",
        rotation_interval_days=45,
        expiry_expected=True,
        emergency_revoke_process="Rotate internal key and restart dependent services in dependency order.",
        where_stored="Secret store per service and environment.",
        where_never_stored="Repo, logs, dashboard payloads.",
        production_live_impact="Internal APIs must reject old keys and fail closed.",
        rotation_test_requirement="Service-to-service auth rotation smoke.",
    ),
    "GATEWAY_INTERNAL_API_KEY": SecretPolicy(
        id="GATEWAY_INTERNAL_API_KEY",
        owner_role="Platform Security",
        environments=("local", "shadow", "production"),
        sensitivity="high",
        rotation_interval_days=45,
        expiry_expected=True,
        emergency_revoke_process="Rotate gateway key and restart BFF/service clients.",
        where_stored="Secret store per environment.",
        where_never_stored="Repo, browser, logs, BFF JSON responses.",
        production_live_impact="Gateway and dashboard BFF must reject stale internal credentials.",
        rotation_test_requirement="Gateway/BFF internal auth smoke.",
    ),
    "ADMIN_TOKEN": SecretPolicy(
        id="ADMIN_TOKEN",
        owner_role="Platform Security / Operations",
        environments=("local", "shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=14,
        expiry_expected=True,
        emergency_revoke_process="Revoke token, invalidate admin sessions, require operator re-approval.",
        where_stored="Short-lived secret store entry or break-glass vault.",
        where_never_stored="Repo, browser local storage, screenshots, logs.",
        production_live_impact="Admin actions must be unavailable until fresh authorization exists.",
        rotation_test_requirement="Admin auth expiry and revoke test.",
    ),
    "ENCRYPTION_KEY": SecretPolicy(
        id="ENCRYPTION_KEY",
        owner_role="Platform Security",
        environments=("shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=180,
        expiry_expected=True,
        emergency_revoke_process="Execute envelope-key rotation and re-encrypt affected material.",
        where_stored="KMS/HSM/Vault transit, never as plain env in production.",
        where_never_stored="Repo, logs, browser, database plaintext columns.",
        production_live_impact="Data decrypt/encrypt path must halt safely if key version is invalid.",
        rotation_test_requirement="Envelope-key version drill in staging.",
    ),
    "DATABASE_URL": SecretPolicy(
        id="DATABASE_URL",
        owner_role="SRE / Database Operations",
        environments=("local", "shadow", "production"),
        sensitivity="high",
        rotation_interval_days=90,
        expiry_expected=True,
        emergency_revoke_process="Rotate DB user/password, drain connections, verify migrations and health.",
        where_stored="Secret store or platform-managed connection reference.",
        where_never_stored="Repo, logs, client-side bundles.",
        production_live_impact="Services must fail readiness until DB auth is healthy.",
        rotation_test_requirement="DB credential rotation smoke and rollback plan.",
    ),
    "POSTGRES_PASSWORD": SecretPolicy(
        id="POSTGRES_PASSWORD",
        owner_role="SRE / Database Operations",
        environments=("local", "shadow", "production"),
        sensitivity="high",
        rotation_interval_days=90,
        expiry_expected=True,
        emergency_revoke_process="Rotate password, restart clients, revoke old role grants.",
        where_stored="Secret store or managed database secret reference.",
        where_never_stored="Repo, logs, dashboard.",
        production_live_impact="Services must not submit orders without DB readiness.",
        rotation_test_requirement="DB password rotation and readiness test.",
    ),
    "REDIS_PASSWORD": SecretPolicy(
        id="REDIS_PASSWORD",
        owner_role="SRE / Platform Security",
        environments=("local", "shadow", "production"),
        sensitivity="high",
        rotation_interval_days=90,
        expiry_expected=True,
        emergency_revoke_process="Rotate Redis credential, restart clients, verify queues and latches.",
        where_stored="Secret store or managed Redis auth reference.",
        where_never_stored="Repo, logs, dashboard.",
        production_live_impact="Trading must block if Redis latch/state cannot be trusted.",
        rotation_test_requirement="Redis auth rotation and fail-closed latch test.",
    ),
    "PAYMENT_STRIPE_SECRET_KEY": SecretPolicy(
        id="PAYMENT_STRIPE_SECRET_KEY",
        owner_role="Billing Operations / Security",
        environments=("shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=60,
        expiry_expected=True,
        emergency_revoke_process="Revoke Stripe secret key, rotate webhook endpoints, pause billing writes.",
        where_stored="Payment secret store entry per environment.",
        where_never_stored="Repo, browser, logs, customer portal payloads.",
        production_live_impact="Commercial gates must fail closed if billing truth is unavailable.",
        rotation_test_requirement="Webhook/payment sandbox rotation test.",
    ),
    "PAYMENT_STRIPE_WEBHOOK_SECRET": SecretPolicy(
        id="PAYMENT_STRIPE_WEBHOOK_SECRET",
        owner_role="Billing Operations / Security",
        environments=("shadow", "production"),
        sensitivity="high",
        rotation_interval_days=60,
        expiry_expected=True,
        emergency_revoke_process="Rotate webhook signing secret and reject old signatures.",
        where_stored="Payment secret store entry per environment.",
        where_never_stored="Repo, logs, webhook responses.",
        production_live_impact="Billing state must not update from unsigned/stale events.",
        rotation_test_requirement="Webhook signature rotation test.",
    ),
    "VAULT_TOKEN": SecretPolicy(
        id="VAULT_TOKEN",
        owner_role="SRE / Security",
        environments=("shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=7,
        expiry_expected=True,
        emergency_revoke_process="Revoke token, rotate child tokens, verify audit log and policies.",
        where_stored="Workload identity or short-lived platform secret mount.",
        where_never_stored="Repo, shell history, logs, CI output.",
        production_live_impact="Services must fail closed if secret retrieval is untrusted.",
        rotation_test_requirement="Vault token renewal/revoke drill.",
    ),
    "KMS_KEY_ID": SecretPolicy(
        id="KMS_KEY_ID",
        owner_role="SRE / Security",
        environments=("shadow", "production"),
        sensitivity="high",
        rotation_interval_days=365,
        expiry_expected=False,
        emergency_revoke_process="Disable compromised key version and re-point aliases after approval.",
        where_stored="KMS alias/reference in config, key material in KMS only.",
        where_never_stored="Repo as key material, logs, browser.",
        production_live_impact="Encrypted data path must block if key reference is invalid.",
        rotation_test_requirement="KMS alias/key-version staging drill.",
    ),
    "CUSTOMER_EXCHANGE_SECRET_REFERENCE": SecretPolicy(
        id="CUSTOMER_EXCHANGE_SECRET_REFERENCE",
        owner_role="Customer Security / Trading Operations",
        environments=("shadow", "production"),
        sensitivity="critical",
        rotation_interval_days=30,
        expiry_expected=True,
        emergency_revoke_process="Revoke customer exchange credential reference and block tenant trading.",
        where_stored="Tenant-scoped secret store reference only.",
        where_never_stored="Browser, repo, logs, analytics, support screenshots.",
        production_live_impact="Affected tenant trading must block until customer re-authorization.",
        rotation_test_requirement="Tenant-scoped reference rotation and cross-tenant leak test.",
    ),
}


ALIASES = {
    "KMS_REFERENCE": "KMS_KEY_ID",
    "KMS_KEY_REF": "KMS_KEY_ID",
    "CUSTOMER_EXCHANGE_SECRET": "CUSTOMER_EXCHANGE_SECRET_REFERENCE",
    "CUSTOMER_API_SECRET": "CUSTOMER_EXCHANGE_SECRET_REFERENCE",
    "CUSTOMER_BITGET_API_SECRET": "CUSTOMER_EXCHANGE_SECRET_REFERENCE",
}

TOKEN_FRAGMENTS = (
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSPHRASE",
    "API_KEY",
    "DATABASE_URL",
    "ENCRYPTION_KEY",
    "KMS",
)


def _normalize_secret_name(name: str) -> str:
    return name.strip().upper().replace("-", "_")


def classify_secret_name(name: str) -> SecretPolicy:
    normalized = _normalize_secret_name(name)
    if normalized in ALIASES:
        normalized = ALIASES[normalized]
    if normalized in SECRET_POLICIES:
        return SECRET_POLICIES[normalized]
    if "CUSTOMER" in normalized and any(x in normalized for x in ("EXCHANGE", "BITGET")):
        return SECRET_POLICIES["CUSTOMER_EXCHANGE_SECRET_REFERENCE"]
    if any(fragment in normalized for fragment in TOKEN_FRAGMENTS):
        return SecretPolicy(
            id=normalized or "UNKNOWN_SECRET",
            owner_role="Security",
            environments=("local", "shadow", "production"),
            sensitivity="high",
            rotation_interval_days=30,
            expiry_expected=True,
            emergency_revoke_process="Treat as unknown sensitive credential: revoke, rotate, and audit usage.",
            where_stored="Secret store pending formal classification.",
            where_never_stored="Repo, browser, logs, screenshots, test fixtures.",
            production_live_impact="Fail closed until owner and rotation policy are assigned.",
            rotation_test_requirement="Add explicit policy and run simulated rotation drill.",
        )
    return SecretPolicy(
        id=normalized or "UNKNOWN_SECRET",
        owner_role="Security",
        environments=("local", "shadow", "production"),
        sensitivity="high",
        rotation_interval_days=30,
        expiry_expected=True,
        emergency_revoke_process="Treat unknown name as sensitive until proven otherwise.",
        where_stored="Secret store pending formal classification.",
        where_never_stored="Repo, browser, logs, screenshots, test fixtures.",
        production_live_impact="Fail closed if used in a production control path.",
        rotation_test_requirement="Classify explicitly before production use.",
    )


def secret_requires_rotation(name: str) -> bool:
    return classify_secret_name(name).rotation_interval_days is not None


def secret_rotation_interval_days(name: str) -> int | None:
    return classify_secret_name(name).rotation_interval_days


def secret_is_expired(
    name: str,
    *,
    last_rotated_at: date | datetime | None,
    as_of: date | datetime | None = None,
) -> bool:
    policy = classify_secret_name(name)
    if policy.rotation_interval_days is None:
        return False
    if last_rotated_at is None:
        return True
    if as_of is None:
        as_of = datetime.now(tz=UTC)
    if isinstance(last_rotated_at, datetime):
        last_date = last_rotated_at.date()
    else:
        last_date = last_rotated_at
    if isinstance(as_of, datetime):
        as_of_date = as_of.date()
    else:
        as_of_date = as_of
    return last_date + timedelta(days=policy.rotation_interval_days) < as_of_date


def secret_reuse_across_env_is_forbidden(name: str) -> bool:
    policy = classify_secret_name(name)
    return len(policy.environments) > 1 and policy.sensitivity in {"high", "critical"}


def build_secret_rotation_audit_payload(
    name: str,
    *,
    owner: str | None = None,
    environment: str,
    reason: str,
    last_rotated_at: date | datetime | None = None,
    as_of: date | datetime | None = None,
) -> dict[str, Any]:
    policy = classify_secret_name(name)
    if as_of is None:
        as_of = datetime.now(tz=UTC)
    return {
        "secret_id": policy.id,
        "owner": owner or policy.owner_role,
        "environment": environment,
        "reason": reason,
        "sensitivity": policy.sensitivity,
        "rotation_required": secret_requires_rotation(name),
        "rotation_interval_days": policy.rotation_interval_days,
        "expired": secret_is_expired(
            name,
            last_rotated_at=last_rotated_at,
            as_of=as_of,
        ),
        "reuse_across_env_forbidden": secret_reuse_across_env_is_forbidden(name),
        "policy": asdict(policy),
    }


def all_secret_policies() -> tuple[SecretPolicy, ...]:
    return tuple(SECRET_POLICIES.values())
