/**
 * Leser-Envelope des API-Gateways (`merge_read_envelope`).
 * @see services/api-gateway/src/api_gateway/gateway_read_envelope.py
 * @see docs/PRODUCTION_READINESS_AND_API_CONTRACTS.md
 */
export type GatewayReadStatus = "ok" | "empty" | "degraded";

export type GatewayReadEnvelope = {
  status: GatewayReadStatus;
  message: string | null;
  empty_state: boolean;
  degradation_reason: string | null;
  next_step: string | null;
  /** Gateway `merge_read_envelope` (api-gateway); fehlt bei aelteren Deployments. */
  read_envelope_contract_version?: number;
};
