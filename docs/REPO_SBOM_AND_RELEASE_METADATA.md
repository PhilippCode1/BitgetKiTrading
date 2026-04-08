# SBOM-Hinweise und Release-Metadaten

Zweck: **Nachvollziehbarkeit** fuer Security- und Compliance-Reviews ohne ein
generiertes SBOM-Artefakt fest im Gitbaum vorzuhalten (verhindert Drift und
Merge-Konflikte).

## Fest im Repo verankerte Manifeste

| Artefakt                      | Inhalt                                                                   |
| ----------------------------- | ------------------------------------------------------------------------ |
| `pnpm-lock.yaml`              | Exakte Node-Abhaengigkeiten des Monorepos                                |
| `constraints-runtime.txt`     | Exakte Python-Laufzeit-Pins (gemeinsamer Kern)                           |
| `requirements-dev.txt`        | Exakte Dev-/CI-Toolchain (pytest, ruff, …)                               |
| `infra/service-manifest.yaml` | Dienstinventar, Ports, ENV-Erwartungen; Abschnitt `release_auditability` |

## Formale SBOM-Erzeugung (CI oder lokal, nicht committen)

**Python** (Beispiel, nach Installation der Zielumgebung):

```bash
pip install cyclonedx-bom
cyclonedx-py environment -o sbom-python.cdx.json
```

**Node** (im Repo-Root nach `pnpm install --frozen-lockfile`):

```bash
pnpm dlx @cyclonedx/cyclonedx-npm@latest --output-file sbom-node.cdx.json
```

Ergebnis als **CI-Artefakt** oder in einem **Release-Bucket** ablegen, nicht im
Hauptbranch pflegen, sofern keine organisatorische Pflicht zum Einchecken besteht.

## Release-Metadaten

- **Versionierung:** Monorepo-Root `package.json` / Workspace `version` sind
  kommunikativ; einzelne Python-Services tragen `version` in `pyproject.toml`.
- **Gates vor Merge/RC:** `docs/ci_release_gates.md`, `tools/release_sanity_checks.py`,
  `docs/LAUNCH_DOSSIER.md` (Stufe G0).
