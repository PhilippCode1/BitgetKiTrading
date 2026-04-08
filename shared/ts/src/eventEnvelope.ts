import { ENVELOPE_SCHEMA_VERSION } from "./contractVersions";
import type { EventBusEventType } from "./eventStreams";

/** Aligniert zu shared/contracts/schemas/event_envelope.schema.json */
export type BitgetInstrumentV1 = {
  schema_version: string;
  canonical_instrument_id: string;
  venue: string;
  market_family: "spot" | "margin" | "futures";
  symbol: string;
  category_key: string;
  product_type?: string | null;
  margin_coin?: string | null;
  margin_account_mode: "cash" | "isolated" | "crossed";
  base_coin?: string | null;
  quote_coin?: string | null;
  settle_coin?: string | null;
  public_ws_inst_type: string;
  private_ws_inst_type?: string | null;
  metadata_source: string;
  metadata_verified: boolean;
  status?: string | null;
  inventory_visible: boolean;
  analytics_eligible: boolean;
  paper_shadow_eligible: boolean;
  live_execution_enabled: boolean;
  execution_disabled: boolean;
  supports_funding: boolean;
  supports_open_interest: boolean;
  supports_long_short: boolean;
  supports_shorting: boolean;
  supports_reduce_only: boolean;
  supports_leverage: boolean;
  uses_spot_public_market_data: boolean;
};

export type EventEnvelopeV1 = {
  schema_version: typeof ENVELOPE_SCHEMA_VERSION;
  event_id: string;
  event_type: EventBusEventType;
  symbol: string;
  instrument?: BitgetInstrumentV1 | null;
  timeframe?: string | null;
  exchange_ts_ms?: number | null;
  ingest_ts_ms: number;
  dedupe_key?: string | null;
  payload: Record<string, unknown>;
  trace: Record<string, unknown>;
};
