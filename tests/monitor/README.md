# Monitor / QA-Hinweise (Prompt 30)

- Produktions-Smoke: `scripts/healthcheck.sh`
- Logs: bei `LOG_FORMAT=json` auf strukturierte Felder `level`, `service`, `timestamp` pruefen.
- Keine API-Keys oder PII in Assertions oder Fixture-Dateien ablegen.
