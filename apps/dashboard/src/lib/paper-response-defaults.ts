import type {
  PaperJournalResponse,
  PaperLedgerResponse,
  PaperMetricsResponse,
  PaperOpenResponse,
  PaperTradesResponse,
} from "@/lib/types";

/**
 * Fallbacks mit vollständigem Gateway-Lesenvelope — gleiche Pflichtfelder wie `merge_read_envelope`.
 * Verhindert `undefined`-Zugriffe auf der Paper-Console bei Teilfehlern oder vor dem ersten Fetch.
 */
export function emptyPaperOpenResponse(): PaperOpenResponse {
  return {
    status: "ok",
    message: null,
    empty_state: true,
    degradation_reason: null,
    next_step: null,
    positions: [],
  };
}

export function emptyPaperTradesResponse(limit = 50): PaperTradesResponse {
  return {
    status: "ok",
    message: null,
    empty_state: true,
    degradation_reason: null,
    next_step: null,
    trades: [],
    limit,
  };
}

export function emptyPaperMetricsResponse(): PaperMetricsResponse {
  return {
    status: "ok",
    message: null,
    empty_state: false,
    degradation_reason: null,
    next_step: null,
    account: null,
    fees_total_usdt: 0,
    funding_total_usdt: 0,
    equity_curve: [],
    account_ledger_recent: [],
  };
}

export function emptyPaperJournalResponse(limit = 40): PaperJournalResponse {
  return {
    status: "ok",
    message: null,
    empty_state: true,
    degradation_reason: null,
    next_step: null,
    events: [],
    limit,
  };
}

export function emptyPaperLedgerResponse(limit = 40): PaperLedgerResponse {
  return {
    status: "ok",
    message: null,
    empty_state: true,
    degradation_reason: null,
    next_step: null,
    entries: [],
    limit,
  };
}
