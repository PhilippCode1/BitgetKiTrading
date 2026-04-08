import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const pathDe = path.join(root, "apps/dashboard/src/messages/de.json");
const pathEn = path.join(root, "apps/dashboard/src/messages/en.json");

const diagnosticDe = {
  surfaces: {
    common: {
      safetyAiToggle: "Sicherheits-KI zur Vertiefung (optional, einklappbar)",
      safetyAiLead:
        "Der vorausgefüllte Kontext enthält technische Hinweise zu dieser Fläche. Antworten sind indikativ — siehe Architektur Prompt 38 und Fehler-Dossier 08.",
      embeddedSafetyLead:
        "Eingebettete Sicherheits-Diagnose: Frage anpassen und senden. Kontext ist mit dieser Oberfläche vorbelegt.",
      refDocLine:
        "Referenz: docs/chatgpt_handoff/08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md · docs/cursor_execution/38_safety_ai_architecture.md",
      sectionCauses: "Wahrscheinliche Ursachen (Priorität je nach Stack)",
      sectionServices: "Typisch betroffene Dienste / Runtime",
      sectionInterfaces: "Schnittstellen & Code-Pfade",
      sectionNext: "Nächste Schritte für Betrieb / Entwicklung",
    },
    consoleChartFetchFailed: {
      title: "Konsole: Marktchart — Abruf fehlgeschlagen",
      lead: "Der Browser konnte den Live-State für Chart-Kerzen nicht laden. Ohne erfolgreichen Fetch bleibt der Chart leer oder zeigt nur den Fehlerzustand des Chart-Widgets.",
      cause1:
        "Dashboard-BFF oder Gateway nicht erreichbar (Netzwerk, TLS, falsche Base-URL).",
      cause2:
        "Authentifizierung/Session am Operator-Ende fehlt oder ist abgelaufen.",
      cause3:
        "Upstream Python/Gateway wirft 5xx oder Timeout — siehe Response-Text und x-request-id.",
      cause4:
        "Symbol/Timeframe wird am Server abgelehnt oder liefert leeren Korpus trotz 200.",
      services:
        "Next.js Dashboard (Server/Client), Gateway HTTP, Python services für Live-State, optional Redis als Live-Puffer.",
      interfaces:
        "Client: fetchLiveState → BFF live-state Route; Server: apps/dashboard API-Routen zum Gateway; Gateway: Live-State-Aggregation.",
      step1:
        "Browser-Netzwerk-Tab: fehlgeschlagene Anfrage, Statuscode und Antworttext notieren.",
      step2:
        "Konsole mit ?diagnostic=1 neu laden; Terminal-Seite parallel prüfen.",
      step3: "stack:check / Gateway-Logs; Health-Seite wenn erreichbar.",
      step4:
        "Nach Fix: Hard-Reload; bei anhaltenden 401/403 Session/Cookies prüfen.",
      suggestedSafetyQuestion:
        "Warum schlägt das Laden des Konsole-Marktcharts (Live-State/Kerzen) fehl? Bitte mögliche Ursachenkette aus Gateway, BFF und Datenpipeline nennen und welche Logs ich zuerst prüfen soll.",
    },
    consoleChartEmpty: {
      title: "Konsole: Marktchart — keine Kerzen",
      lead: "Die Anfrage war erfolgreich, aber die Kerzenliste ist leer. Das ist oft ein Daten- oder Konfigurationsproblem, nicht nur ein UI-Thema.",
      cause1:
        "Für Symbol/Timeframe existieren noch keine aggregierten Kerzen in der Historie.",
      cause2:
        "Market-Stream oder Ingest-Pipeline läuft nicht oder hinkt hinterher.",
      cause3:
        "Demo-/Fixture-Modus: bewusst wenig oder keine Marktdaten für das Instrument.",
      cause4:
        "Gateway normalisiert das Symbol anders — Hinweis „resolved“ unter dem Chart beachten.",
      services:
        "Market ingest, Kerzen-Aggregation/DB, Redis Live-Puffer, Bitget REST/WebSocket je nach Profil.",
      interfaces:
        "Live-State-Endpoint; apps/dashboard fetchLiveState; Backend-Kerzen-Tabellen und Stream-Worker.",
      step1:
        "Anderes liquiditätsträchtiges Symbol und kürzeres Timeframe probieren.",
      step2:
        "Live-Terminal öffnen: Datenfluss-Lineage und Frische-Badges prüfen.",
      step3: "Health: execution_mode, Demo-Hinweise und Service-Liste lesen.",
      step4:
        "Betrieb: Ingest-Logs und letzte erfolgreiche Kerzen-Zeit in der DB prüfen.",
      suggestedSafetyQuestion:
        "Das Konsole-Chart liefert 200 aber keine Kerzen. Welche Pipeline-Stufen (Ingest, DB, Gateway) soll ich zuerst prüfen und welche Symptome passen zu unserem Dossier 08?",
    },
    consoleChartFreshness: {
      title: "Konsole: Marktchart — Marktdaten schlecht oder veraltet",
      lead: "Kerzen sind sichtbar, aber die Frische-Metrik meldet stale, dead oder no_candles. Trading- und Risiko-Entscheidungen sollten das berücksichtigen.",
      cause1:
        "Ticker oder Kerzen-Ingest hat aufgehört oder ist stark verzögert.",
      cause2:
        "Redis Live-Puffer oder Verbindung zum Stream-Consumer ist gestört.",
      cause3:
        "Bitget-API Rate-Limits oder Ausfall; Fallback auf veraltete Snapshots.",
      cause4: "Uhrzeit/Drift zwischen Hosts führt zu falsch hohen Lag-Werten.",
      services:
        "Market-Stream-Service, Redis, Gateway-Frische-Berechnung, ggf. Bitget REST.",
      interfaces:
        "market_freshness im Live-State-JSON; apps/dashboard ConsoleLiveMarketChartSection.",
      step1:
        "Frische-Badge-Status und ggf. diagnostic=1 für Zahlen am Terminal nutzen.",
      step2: "Redis und Stream-Prozesse auf dem Stack prüfen.",
      step3:
        "Vergleich: letzter Preis extern (Exchange) vs. Ticker in der API.",
      step4:
        "Bei bekanntem Wartungsfenster dokumentieren; sonst Incident öffnen.",
      suggestedSafetyQuestion:
        "Die Konsole zeigt schlechte Marktfrische trotz sichtbarer Kerzen. Bitte die wahrscheinlichste technische Ursache und die zu prüfenden Dienste nach unserer Fehlerarchitektur benennen.",
    },
    terminalFetchFailed: {
      title: "Live-Terminal: State-Abruf fehlgeschlagen",
      lead: "HTTP-Reload oder Initial-Fetch für den Terminal-State ist fehlgeschlagen. Chart und Seitenleiste können unvollständig sein.",
      cause1:
        "Gleiche Ursachen wie beim Konsole-Chart-Fetch (Netzwerk, Auth, 5xx).",
      cause2:
        "SSE-Setup beeinflusst nicht den ersten REST-Fetch — zuerst REST isolieren.",
      cause3: "Sehr große Payload oder Timeout auf dem Gateway.",
      cause4: "Lokaler Dev-Server ohne gültige Operator-Umgebungsvariablen.",
      services:
        "Dashboard BFF, Gateway live state, DB/Redis laut health.db / health.redis im State.",
      interfaces:
        "fetchLiveState im Terminal-Client; Live-Terminal-Seite apps/dashboard.",
      step1: "Fehlermeldung im Banner und Rohtext unter diagnostic=1 sichern.",
      step2:
        "health.db und health.redis im Terminal-Header mit Logs abgleichen.",
      step3: "edge-status JSON und Gateway-Reachability prüfen.",
      step4: "Nach Fix Seite neu laden; SSE verbindet ggf. automatisch erneut.",
      suggestedSafetyQuestion:
        "Live-Terminal fetchLiveState schlägt fehl. Bitte eine priorisierte Checkliste aus Gateway, DB und Auth ableiten.",
    },
    terminalStreamStale: {
      title: "Live-Terminal: Echtzeit-Stream ruhig (stale)",
      lead: "Es gab lange keinen Server-Ping über die SSE-Verbindung. Die UI fällt auf HTTP-Polling zurück, kann aber veraltet wirken.",
      cause1: "Gateway LIVE_SSE_ENABLED=false oder SSE bricht nach vorne ab.",
      cause2: "Redis Pub/Sub oder Event-Quelle liefert keine Events mehr.",
      cause3: "Client-Netzwerk unterbricht dauerhaft (Proxy, VPN, Sleep).",
      cause4: "Backfill nach Reconnect noch nicht abgeschlossen.",
      services: "Gateway SSE, Redis, Live-Event-Worker, Nginx/Proxy-Timeouts.",
      interfaces:
        "startManagedLiveEventSource; Gateway SSE-Route; Metadaten liveTerminalMeta.sseEnabled.",
      step1: "Stream-Badge und transportHint-Zeilen am Terminal lesen.",
      step2: "Gateway-Logs auf SSE-Disconnect und Ping-Intervalle prüfen.",
      step3: "LIVE_SSE_ENABLED und Redis-Erreichbarkeit verifizieren.",
      step4:
        "Proxy read_timeout erhöhen oder Polling-Intervall akzeptieren bis Fix live ist.",
      suggestedSafetyQuestion:
        "Terminal-SSE ist stale: welche Komponente soll ich zuerst prüfen (Gateway, Redis, Netzwerk) und welche Symptome bestätigen das?",
    },
    terminalEmptyCandles: {
      title: "Live-Terminal: keine Kerzen geladen",
      lead: "Der Terminal-State enthält keine Kerzen. Lineage und Frische helfen, die Lücke einzuordnen.",
      cause1: "Noch kein erfolgreicher Backfill nach Start oder Reconnect.",
      cause2: "Datenbank-Partition leer für Symbol/TF.",
      cause3: "Signal-/Demo-Pfad ohne Marktdaten.",
      cause4: "Fehlkonfiguration des Watchlist-Symbols.",
      services: "Historie-DB, Ingest, Gateway-Aggregation, ggf. Demo-Seeds.",
      interfaces: "LiveStateResponse.candles; LiveDataLineagePanel Segmente.",
      step1: "Empty-State-Hinweise und lineage summary „OK/total“ lesen.",
      step2: "Anderes Symbol/TF testen.",
      step3: "Health und Ops-Lage auf dieselbe Zeit prüfen.",
      step4: "DB-Abfrage auf letzte Kerze für das Symbol (Betrieb).",
      suggestedSafetyQuestion:
        "Terminal hat 0 Kerzen bei sonst grünem Health-Teil — welche Teilstrecke laut Datenfluss-Dossier zuerst?",
    },
    terminalFreshnessBad: {
      title: "Live-Terminal: Marktfrische kritisch",
      lead: "Frische-Status ist stale, dead oder no_candles — analog Konsole, aber mit Terminal-Lineage-Kontext.",
      cause1: "Ingest-Ausfall oder permanente Verzögerung.",
      cause2:
        "Ticker-Kanal tot, Kerzen noch teilweise vorhanden oder umgekehrt.",
      cause3: "Redis-Flush oder Neustart ohne Wiederanlauf.",
      cause4: "Falsches Markt-Universum / Symbol nicht am Stream angebunden.",
      services: "Market-Stream, Redis, Frische-Berechnung im Gateway.",
      interfaces: "state.market_freshness; freshnessBanner im Terminal-Client.",
      step1:
        "Banner-Text und optionale Diagnosezeilen (diagnostic=1) auswerten.",
      step2: "Mit Konsole-Chart zum gleichen Symbol vergleichen.",
      step3: "Stream und REST parallel prüfen.",
      step4: "Alert-Outbox auf wiederholte Markt-Alarme prüfen.",
      suggestedSafetyQuestion:
        "Terminal-Frische ist kritisch: bitte Root-Cause-Hypothesen mit Bezug zu Redis, Stream und DB liefern.",
    },
    healthPageLoadFailed: {
      title: "Health-Seite: Sammelladefehler",
      lead: "Mindestens einer der parallelen Abrufe (System-Health, offene Alerts, Outbox) ist fehlgeschlagen. Die Seite kann unvollständig sein.",
      cause1: "Gateway nicht erreichbar oder TLS-Fehler.",
      cause2: "Dashboard-Server kann Operator-Secrets nicht auflösen.",
      cause3: "Timeout bei schwerer Health-Aggregation.",
      cause4: "Teilentzug durch Rate-Limit oder WAF.",
      services:
        "Dashboard SSR fetch, Gateway Health-Aggregator, Monitor-Service für Alerts.",
      interfaces:
        "fetchSystemHealthCached, fetchMonitorAlertsOpen, fetchAlertOutboxRecent in health/page.tsx.",
      step1: "Fehlertext unten und Server-Logs des Dashboard-Prozesses prüfen.",
      step2: "Einzelendpunkte im Netzwerk-Tab isolieren.",
      step3: "Ops-Übersicht und edge-status laden.",
      step4:
        "Nach Wiederherstellung Seite neu laden; Sicherheits-KI unten nutzt dashboard_load_error im JSON.",
      suggestedSafetyQuestion:
        "Die Health-Seite wirft beim Laden einen Fehler. Bitte die wahrscheinlichste Ursache zwischen Dashboard-BFF, Gateway und Monitor benennen und konkrete Log-Stellen.",
      safetyBelowHint:
        "Die Sicherheits-Diagnose weiter unten auf dieser Seite enthält bereits dashboard_load_error im Kontext — dort die KI anstoßen, statt doppelt einzubetten.",
    },
    operatorExplainLlmFailed: {
      title: "Operator-Erklär-KI: Anfrage fehlgeschlagen",
      lead: "Der Aufruf von operator-explain ist fehlgeschlagen oder lieferte kein gültiges Ergebnis. Es liegt kein zusätzliches Urteil über Live-Handel vor.",
      cause1: "LLM-Gateway Timeout oder 5xx vom Provider.",
      cause2: "Budget, Rate-Limit oder Modell nicht verfügbar.",
      cause3: "BFF-Validierung: Kontext-JSON zu groß oder ungültig.",
      cause4: "Netzwerkabbruch im Browser.",
      services:
        "Dashboard Route /api/dashboard/llm/operator-explain, Python LLM-Orchestrierung, Provider-API.",
      interfaces:
        "OperatorExplainPanel.tsx; BFF operator-explain; Fehlercodes aus operator-explain-errors.",
      step1: "Fehlermeldung und Trace-IDs (falls sichtbar) kopieren.",
      step2: "Kurze Frage und kleinen Kontext erneut versuchen.",
      step3: "Health: KI-Nutzung und Provider-Status prüfen.",
      step4: "Bei anhaltendem 503 Betrieb informieren (Provider-Ausfall).",
      suggestedSafetyQuestion:
        "operator-explain ist fehlgeschlagen. Bitte mögliche Ursachen (Provider, Timeout, Validierung) und die nächsten zwei Debug-Schritte nennen.",
    },
    openAlertsEscalated: {
      title: "Monitor: eskalierte offene Alerts",
      lead: "Es gibt mindestens einen offenen Alert mit hoher oder kritischer Severität. Das ist ein Signal für unmittelbares Prüfen — nicht nur ein Hinweis.",
      cause1:
        "Automatische Regel hat wiederholt fehlgeschlagen (z. B. Datenlücke, Orderpfad).",
      cause2: "Menschliche Eskalation noch nicht quittiert.",
      cause3: "Abhängiger Dienst liefert noch immer Fehlerzustand.",
      cause4: "Flapping durch instabile Infrastruktur.",
      services:
        "Monitor-Engine, Alert-Outbox/Delivery, betroffene Domänen-Services laut Alert-Titel.",
      interfaces:
        "GET monitor alerts API; Health-Seite Tabelle; ggf. Ops-Runbooks.",
      step1:
        "Schwere und Titel der markierten Zeilen lesen; Zeitstempel prüfen.",
      step2: "Verknüpfte Health-Warnungen und Integrationsmatrix öffnen.",
      step3: "Outbox-Versandstatus und letzte Fehler prüfen.",
      step4:
        "Nach Behebung Alerts schließen oder quittieren laut Betriebsprozess.",
      suggestedSafetyQuestion:
        "Wir haben eskalierte offene Monitor-Alerts. Bitte eine priorisierte Ursachenhypothese und welche Service-Logs ich zuerst öffnen soll.",
    },
  },
};

const diagnosticEn = {
  surfaces: {
    common: {
      safetyAiToggle: "Optional safety-AI deep dive (collapsed)",
      safetyAiLead:
        "Prefilled context includes technical hints for this surface. Answers are indicative — see prompt 38 architecture and error dossier 08.",
      embeddedSafetyLead:
        "Embedded safety diagnosis: adjust the question and submit. Context is pre-seeded for this surface.",
      refDocLine:
        "Reference: docs/chatgpt_handoff/08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md · docs/cursor_execution/38_safety_ai_architecture.md",
      sectionCauses: "Likely causes (priority depends on your stack)",
      sectionServices: "Typically affected services / runtime",
      sectionInterfaces: "Interfaces and code paths",
      sectionNext: "Next steps for ops / engineering",
    },
    consoleChartFetchFailed: {
      title: "Console market chart: fetch failed",
      lead: "The browser could not load live state for chart candles. Without a successful fetch the chart stays empty or only shows the chart widget error.",
      cause1:
        "Dashboard BFF or gateway unreachable (network, TLS, wrong base URL).",
      cause2: "Operator auth/session missing or expired.",
      cause3:
        "Upstream Python/gateway returns 5xx or times out — check body and x-request-id.",
      cause4:
        "Symbol/timeframe rejected server-side or empty body despite 200.",
      services:
        "Next.js dashboard, gateway HTTP, Python live-state services, optional Redis buffer.",
      interfaces:
        "Client fetchLiveState → BFF live-state route; dashboard API routes; gateway aggregation.",
      step1: "Browser network tab: failed request, status, response text.",
      step2: "Reload with ?diagnostic=1; compare live terminal page.",
      step3: "stack:check / gateway logs; health page if reachable.",
      step4: "After fix: hard reload; for 401/403 check session/cookies.",
      suggestedSafetyQuestion:
        "Why is console market chart live-state/candles fetch failing? Please outline gateway/BFF/data pipeline suspects and which logs to open first.",
    },
    consoleChartEmpty: {
      title: "Console market chart: no candles",
      lead: "The request succeeded but the candle list is empty — usually data or configuration, not just UI.",
      cause1: "No aggregated candles yet for this symbol/timeframe.",
      cause2: "Market ingest/stream pipeline stopped or lags heavily.",
      cause3: "Demo/fixture mode deliberately sparse for the instrument.",
      cause4:
        "Gateway normalises symbol differently — note “resolved” under the chart.",
      services:
        "Market ingest, candle DB aggregation, Redis buffer, Bitget REST/WebSocket per profile.",
      interfaces:
        "Live-state endpoint; apps/dashboard fetchLiveState; backend candle tables and workers.",
      step1: "Try a more liquid symbol and a shorter timeframe.",
      step2: "Open live terminal: lineage + freshness badges.",
      step3: "Read health execution mode, demo hints, service list.",
      step4: "Ops: ingest logs and last successful candle timestamp in DB.",
      suggestedSafetyQuestion:
        "Console chart returns 200 but no candles. Which pipeline stages (ingest, DB, gateway) should I check first per dossier 08?",
    },
    consoleChartFreshness: {
      title: "Console market chart: poor or stale market data",
      lead: "Candles render but freshness reports stale, dead, or no_candles. Treat trading/risk decisions accordingly.",
      cause1: "Ticker or candle ingest stopped or heavily delayed.",
      cause2: "Redis live buffer or stream consumer impaired.",
      cause3: "Bitget API limits/outage; stale snapshots.",
      cause4: "Host clock skew inflates lag metrics.",
      services: "Market stream, Redis, gateway freshness calc, Bitget REST.",
      interfaces:
        "market_freshness in live-state JSON; ConsoleLiveMarketChartSection.",
      step1: "Use freshness badge and terminal diagnostic numbers.",
      step2: "Check Redis and stream processes on the stack.",
      step3: "Compare external last price vs API ticker.",
      step4: "Document maintenance windows; otherwise open an incident.",
      suggestedSafetyQuestion:
        "Console shows bad market freshness despite visible candles. Name the most likely technical cause and services to verify per our error architecture.",
    },
    terminalFetchFailed: {
      title: "Live terminal: state fetch failed",
      lead: "HTTP reload or initial fetch for terminal state failed. Chart and side panels may be incomplete.",
      cause1: "Same class as console chart fetch (network, auth, 5xx).",
      cause2: "SSE does not replace first REST fetch — isolate REST first.",
      cause3: "Very large payload or gateway timeout.",
      cause4: "Local dev without valid operator env for dashboard server.",
      services:
        "Dashboard BFF, gateway live state, DB/Redis per health.db/redis in state.",
      interfaces: "fetchLiveState in terminal client; live terminal route.",
      step1: "Capture banner message and raw text with ?diagnostic=1.",
      step2: "Match health.db/redis with logs.",
      step3: "Check edge-status JSON and gateway reachability.",
      step4: "Reload after fix; SSE may reconnect automatically.",
      suggestedSafetyQuestion:
        "Live terminal fetchLiveState fails. Provide a prioritized checklist across gateway, DB, and auth.",
    },
    terminalStreamStale: {
      title: "Live terminal: realtime stream quiet (stale)",
      lead: "No server ping on SSE for a long time. UI falls back to HTTP polling and may look stale.",
      cause1: "Gateway LIVE_SSE_ENABLED=false or SSE breaks upstream.",
      cause2: "Redis pub/sub or event source stopped emitting.",
      cause3: "Client network drops persistently (proxy, VPN, sleep).",
      cause4: "Post-reconnect backfill not finished.",
      services: "Gateway SSE, Redis, live event worker, proxy timeouts.",
      interfaces:
        "startManagedLiveEventSource; gateway SSE route; liveTerminalMeta.sseEnabled.",
      step1: "Read stream badge and transport hints.",
      step2: "Gateway logs for SSE disconnects and ping intervals.",
      step3: "Verify LIVE_SSE_ENABLED and Redis.",
      step4: "Increase proxy read_timeout or accept polling until fixed.",
      suggestedSafetyQuestion:
        "Terminal SSE is stale: which component should I check first (gateway, Redis, network) and which symptoms confirm it?",
    },
    terminalEmptyCandles: {
      title: "Live terminal: no candles loaded",
      lead: "Terminal state has zero candles. Lineage and freshness narrow the gap.",
      cause1: "No successful backfill after start/reconnect yet.",
      cause2: "DB partition empty for symbol/TF.",
      cause3: "Demo path without market data.",
      cause4: "Watchlist symbol misconfigured.",
      services: "History DB, ingest, gateway aggregation, demo seeds.",
      interfaces: "LiveStateResponse.candles; LiveDataLineagePanel segments.",
      step1: "Read empty-state copy and lineage OK/total.",
      step2: "Try another symbol/TF.",
      step3: "Cross-check health and ops at same time.",
      step4: "Ops: SQL last candle for symbol.",
      suggestedSafetyQuestion:
        "Terminal shows 0 candles while parts of health look OK — which lineage segment per dataflow dossier first?",
    },
    terminalFreshnessBad: {
      title: "Live terminal: market freshness critical",
      lead: "Freshness is stale, dead, or no_candles — similar to console but with terminal lineage context.",
      cause1: "Ingest outage or permanent lag.",
      cause2: "Ticker dead while candles partial or vice versa.",
      cause3: "Redis flush/restart without recovery.",
      cause4: "Symbol not wired to stream in market universe.",
      services: "Market stream, Redis, gateway freshness.",
      interfaces:
        "state.market_freshness; freshness banner in terminal client.",
      step1: "Read banner and optional diagnostic lines.",
      step2: "Compare with console chart for same symbol.",
      step3: "Check stream and REST in parallel.",
      step4: "Scan alert outbox for repeated market alerts.",
      suggestedSafetyQuestion:
        "Terminal freshness is critical: hypotheses tying Redis, stream, and DB?",
    },
    healthPageLoadFailed: {
      title: "Health page: aggregate load failed",
      lead: "At least one parallel fetch (system health, open alerts, outbox) failed. The page may be partial.",
      cause1: "Gateway unreachable or TLS error.",
      cause2: "Dashboard server cannot resolve operator secrets.",
      cause3: "Timeout during heavy health aggregation.",
      cause4: "Partial denial via rate limit or WAF.",
      services:
        "Dashboard SSR fetch, gateway health aggregator, monitor for alerts.",
      interfaces:
        "fetchSystemHealthCached, fetchMonitorAlertsOpen, fetchAlertOutboxRecent in health/page.tsx.",
      step1: "Read error text and dashboard server logs.",
      step2: "Isolate endpoints in network tab.",
      step3: "Open ops overview and edge-status.",
      step4:
        "After recovery reload; safety AI below includes dashboard_load_error in JSON.",
      suggestedSafetyQuestion:
        "Health page throws while loading. Most likely cause among BFF, gateway, monitor — and concrete log locations?",
      safetyBelowHint:
        "The safety diagnosis panel below already includes dashboard_load_error in context — run the AI there instead of duplicating inline.",
    },
    operatorExplainLlmFailed: {
      title: "Operator explain AI: request failed",
      lead: "operator-explain call failed or returned no valid result. No extra judgement on live trading.",
      cause1: "LLM gateway timeout or provider 5xx.",
      cause2: "Budget, rate limit, or model unavailable.",
      cause3: "BFF validation: context JSON too large or invalid.",
      cause4: "Browser network drop.",
      services:
        "Dashboard /api/dashboard/llm/operator-explain, Python LLM orchestration, provider API.",
      interfaces:
        "OperatorExplainPanel.tsx; BFF operator-explain; operator-explain-errors.",
      step1: "Copy error text and trace IDs if shown.",
      step2: "Retry with short question and small context.",
      step3: "Health: AI usage and provider status.",
      step4: "Persistent 503 → notify ops (provider outage).",
      suggestedSafetyQuestion:
        "operator-explain failed. Likely causes (provider, timeout, validation) and the next two debug steps?",
    },
    openAlertsEscalated: {
      title: "Monitor: escalated open alerts",
      lead: "At least one open alert has high or critical severity — treat as immediate review, not background noise.",
      cause1: "Automatic rule repeatedly failed (data gap, order path).",
      cause2: "Human escalation not yet acknowledged.",
      cause3: "Dependent service still in error state.",
      cause4: "Flapping infrastructure.",
      services:
        "Monitor engine, alert outbox/delivery, domain services per alert title.",
      interfaces: "Monitor alerts API; health table; ops runbooks.",
      step1: "Read severity/title; check timestamps.",
      step2: "Open related health warnings and integrations matrix.",
      step3: "Check outbox delivery status and last errors.",
      step4: "Close or acknowledge alerts per ops process after fix.",
      suggestedSafetyQuestion:
        "We have escalated open monitor alerts. Prioritised root-cause hypothesis and which service logs to open first?",
    },
  },
};

const de = JSON.parse(fs.readFileSync(pathDe, "utf8"));
const en = JSON.parse(fs.readFileSync(pathEn, "utf8"));
de.diagnostic = diagnosticDe;
en.diagnostic = diagnosticEn;
fs.writeFileSync(pathDe, `${JSON.stringify(de, null, 2)}\n`);
fs.writeFileSync(pathEn, `${JSON.stringify(en, null, 2)}\n`);
console.log("patched diagnostic i18n");
