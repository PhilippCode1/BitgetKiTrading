# Model Registry V2 (Champion / Challenger)

## Zweck

- **Champion**: Run(s), die die Signal-Engine in Produktion fuer ein `model_name` laedt
  (wenn `MODEL_REGISTRY_V2_ENABLED=true`). **Globaler** Champion (`scope_type=global`)
  spiegelt zusaetzlich `promoted_bool` auf `app.model_runs`. **Scoped** Champions
  (Familie, **Cluster** `market_family::market_regime`, Regime, Playbook, **Symbol**, Router)
  existieren nur in der Registry — kein `promoted_bool` fuer diese Slots (Migration `550`, Erweiterung `593`).
- **Challenger**: optionaler Shadow-Slot **pro** `(model_name, role, scope_type, scope_key)`;
  kein Live-Load als Champion.
- **Kalibrierung**: fuer konfigurierte Wahrscheinlichkeitsmodelle (z. B.
  `take_trade_prob`, `market_regime_classifier`) ist bei
  `MODEL_CALIBRATION_REQUIRED=true` ein gueltiger Kalibrierungsstatus
  Voraussetzung fuer Inferenz.

## Datenbank

Migration `infra/migrations/postgres/390_model_registry_v2.sql`:

- Tabelle `app.model_registry_v2` mit `model_name`, `role` (`champion` |
  `challenger`), `run_id`, `calibration_status`, `activated_ts`, Metriken-Spiegel.
- Aenderungen an Slots schreiben zusaetzlich in `app.audit_log` (Learning-Engine).

Migration `infra/migrations/postgres/410_model_champion_lifecycle.sql` (Prompt 29):

- `app.model_champion_history` — Champion-Perioden inkl. `promotion_gate_report`.
- `app.model_stable_champion_checkpoint` — expliziter Rollback-Punkt.

Migration `infra/migrations/postgres/550_model_registry_v2_scoped_slots.sql`:

- Spalten `scope_type` (`global` \| `market_family` \| `market_cluster` \| `market_regime` \| `playbook` \| `router_slot` \| `symbol`),
  `scope_key` (leer bei `global`; `market_cluster`-Key = `familie::regime` kleingeschrieben).
- UNIQUE `(model_name, role, scope_type, scope_key)`.
- Historie + Checkpoint um `scope_type` / `scope_key` erweitert; Checkpoint-PK
  `(model_name, scope_type, scope_key)`.

Governance (Promotion, Drift, Rollback): [model_lifecycle_governance.md](model_lifecycle_governance.md).

## Aufloesung in der Signal-Engine (Take-Trade)

- Ohne `MODEL_REGISTRY_SCOPED_SLOTS_ENABLED`: es wird nur der **globale** Champion
  geladen (`scope_type=global`, `scope_key=''`).
- Mit `MODEL_REGISTRY_SCOPED_SLOTS_ENABLED=true`: Reihenfolge der Versuche:
  `router_slot` (wenn gesetzt) → `playbook` → **`symbol`** → **`market_cluster`** (`familie::regime`)
  → `market_regime` → `market_family` → **global**.
- **Hinweis:** Take-Trade laeuft heute **vor** `_apply_specialist_stack`; `playbook_id`
  ist in dieser Phase typischerweise noch leer — Playbook-scoped Champions sind fuer
  spaetere Pipeline-Erweiterungen oder andere Koepfe vorgesehen. Familie + Regime sind
  zur Laufzeit verfuegbar.

## Fallback / Konservativ

- Fehlt ein passender Scoped-Slot, greift automatisch der **globale** Champion
  (sofern gesetzt).
- **Rollback:** `POST /learning/registry/v2/rollback-stable` mit optionalem
  `scope_type` / `scope_key` (Default global) setzt Champion auf den stabilen
  Checkpoint **dieses** Scopes — ohne Promotions-Gates (Notfall).
- Optional: `MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK` rollt nur den
  **globalen** Checkpoint fuer `MODEL_REGISTRY_AUTO_ROLLBACK_MODEL_NAME` zurueck.

## Umgebungsvariablen

| Variable                                           | Bedeutung                                                                                                                                                                                                      |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MODEL_REGISTRY_V2_ENABLED`                        | Signal-Engine: Registry statt nur `promoted_bool`.                                                                                                                                                             |
| `MODEL_REGISTRY_SCOPED_SLOTS_ENABLED`              | Signal-Engine: scoped Champion-Aufloesung (s. oben).                                                                                                                                                           |
| `MODEL_CHAMPION_NAME`                              | Erwarteter Champion-`model_name` fuer Take-Trade-Pfad.                                                                                                                                                         |
| `MODEL_CALIBRATION_REQUIRED`                       | `true`: ohne Kalibrierung kein produktiver Einsatz.                                                                                                                                                            |
| `MODEL_PROMOTION_GATES_ENABLED`                    | `true`: Champion nur bei erfuellten Schwellen.                                                                                                                                                                 |
| `MODEL_PROMOTION_MANUAL_OVERRIDE_ENABLED`          | `false`: keine Break-Glass-Overrides per Body.                                                                                                                                                                 |
| `MODEL_REGISTRY_MUTATION_SECRET`                   | Wenn **nicht leer**: alle **mutierenden** Registry-V2-Routen der Learning-Engine verlangen Header `X-Model-Registry-Mutation-Secret` mit exakt diesem Wert (Chat/Telegram ohne Secret koennen nicht mutieren). |
| `MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK` | Optional Rollback global bei `hard_block`.                                                                                                                                                                     |

Zusaetzliche Take-Trade-Promotion-Flags: siehe [model_lifecycle_governance.md](model_lifecycle_governance.md).

## Learning-Engine API (intern)

- `GET /learning/registry/v2/slots` — alle Slots inkl. `scope_type`, `scope_key`.
- `POST /learning/registry/v2/champion` — Body u. a. `model_name`, `run_id`,
  `scope_type`, `scope_key` (Default global), optional Override-Felder; **Mutation-Secret** falls konfiguriert.
- `POST /learning/registry/v2/challenger` — analog.
- `POST /learning/registry/v2/stable-checkpoint` — optional `scope_type`, `scope_key`.
- `POST /learning/registry/v2/rollback-stable` — optional `scope_type`, `scope_key`.
- `DELETE .../champion` — Query `model_name`, optional `scope_type`, `scope_key`, `changed_by`.
- `DELETE .../challenger` — analog.

**Globaler** Champion: setzt `promoted_bool=true` fuer den Run und hebt Promotion
anderer Runs desselben `model_name` auf. **Scoped** Champion: kein `promoted_bool`.

## Dashboard / Gateway

- `GET /v1/learning/models/registry-v2` (API-Gateway) — read-only Tabelle im Learning-Dashboard
  inkl. Scope-Spalten. **Keine** Registry-Mutation ueber das Dashboard; Aenderungen nur
  ueber Learning-API mit Governance-Secret (oder internem Deploy-Tool).

## Betrieb (Kurz-Runbook)

1. Migrationen `390`, `410`, **`550`** auf der App-DB ausfuehren (550 Voraussetzung fuer neue Upserts/Queries mit Scope). Bei leerem **lokalen** Stack optional Demo-Registry: **`postgres_demo/912_demo_local_learning_registry_seed.sql`** nur mit `BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true` und `migrate.py --demo-seeds` (nicht Shadow/Prod).
2. `MODEL_REGISTRY_V2_ENABLED=true`, optional `MODEL_REGISTRY_SCOPED_SLOTS_ENABLED`,
   `MODEL_CHAMPION_NAME`, ggf. `MODEL_CALIBRATION_REQUIRED=true`.
3. In Produktion: `MODEL_REGISTRY_MUTATION_SECRET` setzen und nur vertrauenswuerdigen
   Aufrufern den Header geben (Gateway-Proxy serverseitig).
4. Nach Training: Champion(s) setzen — global als Fallback, scoped nur mit Evidenz
   und passenden Gates (`docs/model_lifecycle_governance.md`).
