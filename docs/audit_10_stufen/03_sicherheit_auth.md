# Teil 3/10: Sicherheit und Authentifizierung

---

## 1. Interne Dienst-zu-Dienst-Auth (stark fuer Ops-Stack)

```31:71:shared/python/src/shared_py/service_auth.py
def internal_service_auth_required(settings: Any) -> bool:
    configured = bool(_normalized_internal_key(settings))
    return configured or bool(getattr(settings, "production", False))


def assert_internal_service_auth(
    settings: Any,
    x_internal_service_key: str | None,
) -> InternalServiceAuthContext:
    expected = _normalized_internal_key(settings)
    presented = str(x_internal_service_key or "").strip()
    ...
    if presented != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INTERNAL_AUTH_REQUIRED",
                "message": (
                    "Direkter Servicezugriff erfordert den internen Service-Key "
                    f"im Header `{INTERNAL_SERVICE_HEADER}`."
                ),
            },
        )
```

**Bewertung:** Klarer Mechanismus; in **Production** ohne Key → 503/401-Pfade moeglich — **gut fuer Microservices**.

---

## 2. Fehlende Schicht: Endkunden-Login / OAuth / Session

Im Audit wurde **kein** vollstaendiges **Kunden-Auth-System** (z. B. OIDC, Passwort+2FA, Session-Store) in einem dedizierten `services/customer-auth` gefunden. Das Modul-Mate-Produkt (Prompt 2/6) **verlangt** das fuer Web.

**Beweis indirekt:** Teil 9 (kein `web/`-Frontend); kommerzielle Tabellen existieren (Teil 5), aber **kein** nachweisbarer Auth-Flow im Python-Tree wie in typischen FastAPI-User-Routers mit JWT-Cookies.

**Bewertung Oberflaeche/Sicherheit:** **niedrig** bis kein lieferbares Login-Produkt.

---

## 3. Produktions-Gates in CI

```62:64:.github/workflows/ci.yml
      - name: Prod/Shadow ENV template security gate
        run: python3 tools/check_production_env_template_security.py
```

**Bewertung:** Supply-Chain/ENV-Checks sind **positiv**; ersetzen keine Threat-Modelle fuer oeffentliche APIs.

---

## 4. Teilbewertung Teil 3

| Dimension                            | Stufe (1–10) | Kurzbegruendung                                                                          |
| ------------------------------------ | ------------ | ---------------------------------------------------------------------------------------- |
| Interne Service-Auth                 | **7**        | Header-Key, Production-Pflichtlogik                                                      |
| Endnutzer-Auth / Mandantenfaehigkeit | **2**        | Nicht als shippable Produkt ersichtlich                                                  |
| Secrets in Logs                      | **6**        | Muster in LLM-Forward ohne Key-Log; Live-Broker Hinweise ohne Secret-Werte in `describe` |

---

**Naechste Datei:** `04_trading_execution.md`
