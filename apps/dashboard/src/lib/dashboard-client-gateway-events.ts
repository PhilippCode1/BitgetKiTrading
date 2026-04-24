import type { FetchErrorKind } from "./user-facing-fetch-error";

/** Konsistenter Name fuer window CustomEvents (BFF/ Gateway-Failures im Browser). */
export const DASHBOARD_GATEWAY_CLIENT_FAILURE = "dashboard-gateway-client-failure";

export type GatewayClientFailureDetail = Readonly<{
  kind: FetchErrorKind;
  code: string | null;
  path: string;
}>;
