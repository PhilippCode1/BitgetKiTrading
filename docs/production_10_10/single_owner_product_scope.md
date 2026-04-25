# Single-Owner Product Scope (Philipp-only)

## Verbindliche Produktausrichtung

`bitget-btc-ai` wird ausschliesslich privat von **Philipp Crljic** genutzt.
Es gibt kein SaaS-Ziel, keine externen Kunden, kein Billing-, Pricing- oder
Payment-Produkt.

## Aktiver Produktkern

- Deutsche Main Console fuer Betrieb, Safety, Risk, Reconcile und Evidence.
- Owner-/Admin-Gates fuer private Live-Freigaben.
- Fail-closed bei Unsicherheit.

## Legacy-/Historisch-Bereiche

Fruehere Customer-/Billing-/Commerce-Pfade bleiben nur als historische Artefakte
im Repository und sind in aktiver Nutzung gesperrt:

- `/portal/*`
- `/console/account/billing`
- `/console/account/payments`
- `/console/admin/billing`
- `/console/admin/commerce-payments`
- `/console/admin/customers/*`
- `/console/admin/contracts`

Die Dashboard-Middleware leitet diese Pfade auf `/console` um.

## Scope-Cleanup-Entscheidungen

- **Nicht blind loeschen:** Legacy-Code bleibt fuer Nachvollziehbarkeit/Forensik.
- **Aktiv deaktivieren:** keine Navigation auf Verkaufs-/Kundenpfade.
- **Begriffe entkoppeln:** Sicherheitsgates bleiben erlaubt, werden aber als
  Owner-/Private-Gates verstanden und nicht als Verkaufslogik.

## Sicherheitsregel

Kein Live-Trading darf von Payment-/Billing-Status abhaengen. Wenn ein altes
Gate historisch aus diesem Kontext stammt, muss es als Owner-Safety-Gate
weitergefuehrt oder deaktiviert werden.
