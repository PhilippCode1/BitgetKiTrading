import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..", "src", "messages");

const DATA_DE = {
  title: "Live-Datenlage",
  subtitle:
    "Sofort erkennbar: Ausführungsspur, Marktdaten/Feed, Alter der letzten Einspielung, Pipeline-Vollständigkeit — ohne Live-Vortäuschung.",
  executionShort: "Spur",
  laneHint: "Paper/Shadow/Live bezieht sich auf die Ausführungskonfiguration, nicht automatisch auf jedes einzelne Dataset.",
  dataBadgeHint:
    "Markt- bzw. Feed-Realität für diese Ansicht (Kerzen, API-Listen, Health-Snapshot …).",
  lane: {
    live: "LIVE (Echtgeld-Pfad möglich)",
    shadow: "SHADOW",
    paper: "PAPER",
    unknown: "Spur unbekannt / gemischt",
  },
  badge: {
    LIVE: "LIVE-Marktdaten (frisch)",
    SHADOW: "SHADOW-Kontext",
    PAPER: "PAPER-Kontext",
    NO_LIVE: "KEINE LIVE-MARKTDATEN",
    STALE: "VERALTETE MARKTDATEN",
    PARTIAL: "TEILWEISE VERFÜGBAR",
    DEGRADED_READ: "EINGESCHRÄNKT (Lesen)",
    ERROR: "LADEN FEHLGESCHLAGEN",
    LOADING: "PRÜFE …",
    SIGNAL_FEED_EMPTY: "KEINE SIGNALZEILEN (Filter/Leerstand)",
  },
  sourceLabel: "Datenquelle",
  source: {
    liveStateGateway: "API-Gateway GET /v1/live/state (Kerzen, Frische, Lineage)",
    healthSnapshot: "API-Gateway GET /v1/system/health (Plattform-Snapshot)",
    signalsApi: "API-Gateway GET /v1/signals/recent (Signalliste — kein Ersatz für Kerzen-Live)",
    brokerApi: "Live-Broker-APIs (Runtime, Orders, Fills — kein Kerzenstream)",
  },
  lastMarketUpdate: "Letzte Marktdaten-Einspielung",
  lastUpdatedNever: "unbekannt / keine Kerzen-Zeit",
  lastUpdatedAgo: "vor {seconds}s",
  serverReference: "Server-Referenzzeit (Antwort)",
  serverClockAgo: "Serveruhr vor {seconds}s",
  qualityLabel: "Datenqualität (Markt)",
  completenessLabel: "Datenvollständigkeit (Pipeline)",
  completenessValue: "{pct}% ({ok} von {total} Strecken mit Daten)",
  completenessNa: "für diese Ansicht nicht berechnet (keine Lineage)",
  streamLabel: "Stream / Transport",
  missingStreams: "Leere oder fehlende Datenstrecken (segment_id)",
  affected: "Betroffene Bereiche",
  areaChart: "Chart & Kerzen",
  areaSignals: "Signale & Overlays",
  areaNews: "News & Marker",
  areaPaper: "Paper-Panel",
  areaSignalTable: "Signaltabelle",
  areaSignalFilters: "Filter & Facetten",
  areaBrokerPanels: "einige Broker-Panels",
  hintDemoFixture:
    "Hinweis: Demo-/Fixture-Pfade aktiv — die Plattform blendet keinen vollen Live-Börsenpfad vor.",
  hintDegradedMessage: "Gateway: {msg}",
  hintDegradedGeneric:
    "Gateway meldet eingeschränktes Lesen — weniger Felder oder ältere Stände möglich.",
  healthOverviewLead:
    "Plattformweite Kerzen-/Signal-Zeitstempel aus Health — nicht dasselbe wie das Symbol im Chart.",
  muMetaLead:
    "Marktübersicht: Katalog-Snapshot unten; Kerzen-Live gilt nur für das gewählte Chart-Symbol.",
  signalsFeedLead:
    "Die Tabelle zeigt gefilterte Signale aus der API — leer kann an Filtern oder fehlender Pipeline liegen, nicht an deinem Browser.",
  signalsNextStep: "Gateway-Hinweis: {step}",
  brokerLead:
    "Broker-Seite: {sections} API-Sektionen meldeten Fehler — einzelne Karten können leer oder veraltet sein.",
  brokerSnapshotTs: "Runtime-Snapshot-Zeitpunkt: {ts}",
  demoFixturePill: "Demo/Fixture",
  degradedReadPill: "Lesen eingeschränkt",
};

const DATA_EN = {
  title: "Live data posture",
  subtitle:
    "Execution lane, market/feed reality, last ingest age, pipeline completeness — no pretending live when it is not.",
  executionShort: "Lane",
  laneHint:
    "Paper/shadow/live describes execution configuration, not every dataset automatically.",
  dataBadgeHint:
    "Market or feed reality for this surface (candles, API lists, health snapshot…).",
  lane: {
    live: "LIVE (real-money path possible)",
    shadow: "SHADOW",
    paper: "PAPER",
    unknown: "Lane unknown / mixed",
  },
  badge: {
    LIVE: "LIVE market data (fresh)",
    SHADOW: "SHADOW context",
    PAPER: "PAPER context",
    NO_LIVE: "NO LIVE MARKET DATA",
    STALE: "STALE MARKET DATA",
    PARTIAL: "PARTIALLY AVAILABLE",
    DEGRADED_READ: "DEGRADED (read)",
    ERROR: "LOAD FAILED",
    LOADING: "CHECKING…",
    SIGNAL_FEED_EMPTY: "NO SIGNAL ROWS (filters/empty pipeline)",
  },
  sourceLabel: "Data source",
  source: {
    liveStateGateway: "API gateway GET /v1/live/state (candles, freshness, lineage)",
    healthSnapshot: "API gateway GET /v1/system/health (platform snapshot)",
    signalsApi:
      "API gateway GET /v1/signals/recent (signal list — not a candle live feed)",
    brokerApi: "Live-broker APIs (runtime, orders, fills — not a candle stream)",
  },
  lastMarketUpdate: "Last market ingest",
  lastUpdatedNever: "unknown / no candle timestamp",
  lastUpdatedAgo: "{seconds}s ago",
  serverReference: "Server reference time (response)",
  serverClockAgo: "server clock {seconds}s ago",
  qualityLabel: "Data quality (market)",
  completenessLabel: "Completeness (pipeline)",
  completenessValue: "{pct}% ({ok} of {total} segments with data)",
  completenessNa: "not computed for this surface (no lineage)",
  streamLabel: "Stream / transport",
  missingStreams: "Missing or empty pipeline segments (segment_id)",
  affected: "Affected areas",
  areaChart: "Chart & candles",
  areaSignals: "Signals & overlays",
  areaNews: "News & markers",
  areaPaper: "Paper panel",
  areaSignalTable: "Signal table",
  areaSignalFilters: "Filters & facets",
  areaBrokerPanels: "some broker panels",
  hintDemoFixture:
    "Note: demo/fixture paths are active — the UI does not claim a full live exchange path.",
  hintDegradedMessage: "Gateway: {msg}",
  hintDegradedGeneric:
    "Gateway reports degraded reads — fewer fields or older snapshots possible.",
  healthOverviewLead:
    "Platform candle/signal timestamps from health — not the same as the chart symbol.",
  muMetaLead:
    "Market overview: catalog snapshot below; candle live applies only to the selected chart symbol.",
  signalsFeedLead:
    "The table shows filtered API signals — empty can mean filters or a dry pipeline, not your browser.",
  signalsNextStep: "Gateway hint: {step}",
  brokerLead:
    "Broker page: {sections} API sections failed — some cards may be empty or stale.",
  brokerSnapshotTs: "Runtime snapshot time: {ts}",
  demoFixturePill: "Demo/fixture",
  degradedReadPill: "Degraded read",
};

function patch(file, data) {
  const p = path.join(root, file);
  const j = JSON.parse(fs.readFileSync(p, "utf8"));
  j.live.dataSituation = data;
  fs.writeFileSync(p, JSON.stringify(j, null, 2) + "\n", "utf8");
}

patch("de.json", DATA_DE);
patch("en.json", DATA_EN);
console.log("merged live.dataSituation i18n");
