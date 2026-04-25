import type { LiveBrokerRuntimeItem } from "@/lib/types";

export type PrivateCredentialStatus =
  | "missing"
  | "placeholder"
  | "configured_redacted"
  | "demo_only"
  | "readonly_verified"
  | "trading_permission_detected"
  | "withdrawal_permission_detected"
  | "invalid"
  | "expired_or_revoked"
  | "rotation_required"
  | "live_write_blocked"
  | "live_write_eligible_after_all_gates";

export type PrivateCredentialView = {
  status: PrivateCredentialStatus;
  demoModus: boolean;
  readOnlyGeprueft: boolean;
  tradingPermissionErkannt: boolean;
  withdrawalPermissionErkannt: boolean | null;
  liveWriteBlocked: boolean;
  liveWriteEligibleAfterAllGates: boolean;
  letztePruefung: string | null;
  blockgruendeDe: string[];
  naechsterSichererSchrittDe: string;
  credentialHints: {
    apiKey: string;
    apiSecret: string;
    passphrase: string;
  };
};

function maskHint(v: string | null | undefined): string {
  const raw = (v ?? "").trim();
  if (!raw) return "missing";
  if (/change_me|example|placeholder|<.+>/i.test(raw)) return "placeholder";
  if (raw.length <= 6) return "***";
  return `${raw.slice(0, 2)}***${raw.slice(-2)}`;
}

export function buildPrivateCredentialViewModel(
  runtime: LiveBrokerRuntimeItem | null,
): PrivateCredentialView {
  if (!runtime) {
    return {
      status: "missing",
      demoModus: false,
      readOnlyGeprueft: false,
      tradingPermissionErkannt: false,
      withdrawalPermissionErkannt: null,
      liveWriteBlocked: true,
      liveWriteEligibleAfterAllGates: false,
      letztePruefung: null,
      blockgruendeDe: [
        "Bitget-Backend nicht verbunden oder keine Runtime-Daten verfügbar.",
        "Live bleibt fail-closed blockiert.",
      ],
      naechsterSichererSchrittDe:
        "Gateway-/BFF-Verbindung prüfen und danach Read-only-Status neu laden.",
      credentialHints: {
        apiKey: "missing",
        apiSecret: "server_only",
        passphrase: "server_only",
      },
    };
  }

  const s = runtime?.bitget_private_status;
  const demo = Boolean(s?.demo_mode);
  const configured = s?.private_api_configured === true;
  const authOk = s?.private_auth_ok === true;
  const authFail =
    s?.private_auth_classification === "invalid" ||
    s?.private_auth_classification === "expired_or_revoked";
  const withdrawalDetected =
    s?.private_auth_classification === "withdrawal_permission_detected"
      ? true
      : null;
  const tradingDetected =
    s?.private_auth_classification === "trading_permission_detected";
  const readOnlyChecked = Boolean(s?.private_auth_ok ?? false);

  const blockgruende: string[] = [];
  let status: PrivateCredentialStatus = "missing";
  if (!configured) {
    blockgruende.push("Bitget Private-Credentials fehlen oder sind unvollständig.");
  } else {
    status = "configured_redacted";
  }
  if (demo) {
    status = "demo_only";
    blockgruende.push("Demo-Modus aktiv; kein echter Live-Betrieb.");
  }
  if (readOnlyChecked && authOk) {
    status = "readonly_verified";
  }
  if (tradingDetected) {
    status = "trading_permission_detected";
  }
  if (withdrawalDetected) {
    status = "withdrawal_permission_detected";
    blockgruende.push("Withdrawal-Permission erkannt (P0, Live blockiert).");
  }
  if (authFail) {
    status = s?.private_auth_classification === "expired_or_revoked" ? "expired_or_revoked" : "invalid";
    blockgruende.push("Private Authentifizierung ungültig oder widerrufen.");
  }
  const liveFlagsOn =
    runtime?.execution_mode === "live" &&
    runtime?.live_trade_enable === true &&
    runtime?.live_order_submission_enabled === true;
  const allGatesOk =
    runtime?.operator_live_submission?.lane === "live_lane_ready" &&
    runtime?.safety_latch_active !== true &&
    (runtime?.active_kill_switches?.length ?? 0) === 0;
  const eligible =
    tradingDetected && !withdrawalDetected && authOk && liveFlagsOn && allGatesOk;
  const liveWriteBlocked = !eligible;
  if (eligible) {
    status = "live_write_eligible_after_all_gates";
  } else {
    if (!["missing", "invalid", "expired_or_revoked", "withdrawal_permission_detected"].includes(status)) {
      status = "live_write_blocked";
    }
    if (!liveFlagsOn) {
      blockgruende.push("Live-Write-Flags sind nicht vollständig aktiv.");
    }
    if (!allGatesOk) {
      blockgruende.push("Nicht alle Live-Gates stehen auf grün.");
    }
  }

  return {
    status,
    demoModus: demo,
    readOnlyGeprueft: readOnlyChecked,
    tradingPermissionErkannt: tradingDetected,
    withdrawalPermissionErkannt: withdrawalDetected,
    liveWriteBlocked,
    liveWriteEligibleAfterAllGates: !liveWriteBlocked,
    letztePruefung: runtime?.created_ts ?? null,
    blockgruendeDe: blockgruende,
    naechsterSichererSchrittDe:
      "Read-only-Diagnose, Gates und Reconcile prüfen; Live erst nach kompletter Freigabe.",
    credentialHints: {
      apiKey: maskHint(s?.credential_profile),
      apiSecret: "server_only",
      passphrase: "server_only",
    },
  };
}
