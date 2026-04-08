# Lokaler Referenz-Start (Kurzverweis)

Der **verbindliche** Schritt-fuer-Schritt-Leitfaden mit ENV-Tabelle, JWT und Akzeptanztests steht hier:

**[docs/LOCAL_START_MINIMUM.md](docs/LOCAL_START_MINIMUM.md)**

**Standardweg (Windows, ein Befehl):** nach angelegter `.env.local` und `pnpm install` → `pnpm dev:up` (mintet JWT, startet Compose, wartet auf Healthchecks).

**Gruen pruefen:** `pnpm smoke` bzw. `pnpm stack:check`.
