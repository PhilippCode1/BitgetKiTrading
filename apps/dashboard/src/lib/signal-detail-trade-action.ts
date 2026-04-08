/**
 * trade_action → i18n (pages.signalsDetail.tradeActions.*).
 */

const NORMALIZE = (s: string) => s.trim().toLowerCase().replace(/-/g, "_");

const TO_KEY: Readonly<Record<string, string>> = {
  do_not_trade: "doNotTrade",
  no_trade: "doNotTrade",
  abstain: "abstain",
  enter_long: "enterLong",
  enter_short: "enterShort",
  exit_long: "exitLong",
  exit_short: "exitShort",
  reduce_long: "reduceLong",
  reduce_short: "reduceShort",
  hold: "hold",
  wait: "wait",
};

const BASE = "pages.signalsDetail.tradeActions";

export type TradeActionI18nRef =
  | { key: string }
  | { key: string; vars: { raw: string } };

export function resolveTradeActionI18n(
  tradeAction: string | null | undefined,
): TradeActionI18nRef {
  const raw = (tradeAction ?? "").trim();
  if (!raw) return { key: `${BASE}.unset` };
  const n = NORMALIZE(raw);
  const short = TO_KEY[n];
  if (short) return { key: `${BASE}.${short}` };
  return { key: `${BASE}.unfamiliar`, vars: { raw } };
}
