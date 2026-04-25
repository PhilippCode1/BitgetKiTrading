import { buildPrivateCredentialViewModel } from "@/lib/private-credential-view-model";
import type { LiveBrokerRuntimeItem } from "@/lib/types";

function mkRuntime(
  patch: Partial<LiveBrokerRuntimeItem> = {},
): LiveBrokerRuntimeItem {
  return {
    reconcile_snapshot_id: "rec-1",
    status: "ok",
    execution_mode: "paper",
    runtime_mode: "paper",
    strategy_execution_mode: "paper",
    upstream_ok: true,
    paper_path_active: true,
    shadow_trade_enable: false,
    shadow_enabled: false,
    shadow_path_active: false,
    live_trade_enable: false,
    live_submission_enabled: false,
    live_order_submission_enabled: false,
    decision_counts: {},
    details: {},
    order_status_counts: {},
    active_kill_switches: [],
    operator_live_submission: {
      lane: "live_lane_unknown",
      reasons_de: [],
      safety_kill_switch_count: 0,
      safety_latch_active: false,
    },
    created_ts: "2026-04-25T18:00:00Z",
    ...patch,
  };
}

describe("private credential view model", () => {
  it("gibt unknown backend deutsch als nicht verbunden aus", () => {
    const vm = buildPrivateCredentialViewModel(null);
    expect(vm.liveWriteBlocked).toBe(true);
    expect(vm.blockgruendeDe.join(" ")).toMatch(/nicht verbunden/i);
  });

  it("maskiert api key im payload", () => {
    const vm = buildPrivateCredentialViewModel(
      mkRuntime({
        bitget_private_status: {
          ui_status: "ok",
          bitget_connection_label: "ok",
          credential_profile: "AK12345678",
          private_api_configured: true,
          private_auth_ok: true,
        },
      }),
    );
    expect(vm.credentialHints.apiKey).not.toBe("AK12345678");
    expect(vm.credentialHints.apiSecret).toBe("server_only");
  });

  it("withdrawal permission blockiert live write fail-closed", () => {
    const vm = buildPrivateCredentialViewModel(
      mkRuntime({
        execution_mode: "live",
        live_trade_enable: true,
        live_order_submission_enabled: true,
        operator_live_submission: {
          lane: "live_lane_ready",
          reasons_de: [],
          safety_kill_switch_count: 0,
          safety_latch_active: false,
        },
        bitget_private_status: {
          ui_status: "ok",
          bitget_connection_label: "ok",
          private_api_configured: true,
          private_auth_ok: true,
          private_auth_classification: "withdrawal_permission_detected",
        },
      }),
    );
    expect(vm.status).toBe("withdrawal_permission_detected");
    expect(vm.liveWriteBlocked).toBe(true);
  });

  it("loading/empty zustand ist nicht gruen und hat sicheren naechsten schritt", () => {
    const vm = buildPrivateCredentialViewModel(null);
    expect(vm.status).toBe("missing");
    expect(vm.liveWriteEligibleAfterAllGates).toBe(false);
    expect(vm.naechsterSichererSchrittDe).toMatch(/prüfen|pruefen/i);
  });
});
