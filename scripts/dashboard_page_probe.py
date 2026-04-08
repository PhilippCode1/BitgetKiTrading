#!/usr/bin/env python3
"""
HTTP-Smoke fuer Dashboard-HTML: prueft Kernrouten auf 200 und typische Shell-Marker.
Kein Browser — fuer CI/Monitoring ohne Playwright.

Exit 1 bei Netzwerkfehler, HTTP!=200, fehlendem Shell-Marker oder verbotenen Fehlertexten.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request


def fetch(url: str, timeout: float = 25.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "dashboard-page-probe/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


FORBIDDEN_SNIPPETS = [
    "Application error",
    "missing required error components",
    "DASHBOARD_GATEWAY_AUTHORIZATION fehlt",
]


def page_ok(html: str, path: str) -> tuple[bool, str]:
    """Konsolen-HTML vs. oeffentliche Marketing-Seite."""
    is_public = path.rstrip("/") in ("", "/") or path.startswith("/welcome")
    if is_public:
        if "public-shell" not in html:
            return False, "fehlt public-shell (Marketing-Shell?)"
        if "<h1" not in html.lower():
            return False, "fehlt h1 (Startseite leer?)"
    else:
        if "dash-sidebar" not in html and "dash-main" not in html:
            return False, "fehlt dash-sidebar/dash-main (kein Dashboard-Shell?)"
        if "<h1" not in html.lower():
            return False, "fehlt h1 (Seite leer/Fehler?)"
    for snip in FORBIDDEN_SNIPPETS:
        if snip in html:
            return False, f"verbotener Text: {snip!r}"
    # Harte rote Fehlerklasse im Hauptinhalt (nicht absolut zuverlaessig, aber guter Indikator)
    if 'class="msg-err' in html or "class='msg-err" in html:
        if re.search(r"<main[^>]*>[\s\S]*msg-err", html, re.I):
            return False, "msg-err innerhalb main"
    return True, ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:3000", help="Dashboard-Origin")
    p.add_argument(
        "--paths",
        nargs="*",
        default=[
            "/",
            "/console",
            "/console/account",
            "/console/account/broker",
            "/console/health",
            "/console/integrations",
            "/console/signals",
            "/console/learning",
            "/console/live-broker",
            "/console/approvals",
            "/console/ops",
            "/console/usage",
        ],
    )
    args = p.parse_args()
    base = args.base_url.rstrip("/")

    failed = False
    print("=== dashboard_page_probe ===")
    print(f"base_url={base}")
    for path in args.paths:
        url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
        try:
            code, html = fetch(url)
            ok, reason = page_ok(html, path)
            status = "OK" if code == 200 and ok else "FAIL"
            print(f"[{status}] {url} HTTP {code} {reason or ''}".rstrip())
            if code != 200 or not ok:
                failed = True
        except urllib.error.HTTPError as e:
            print(f"[FAIL] {url} HTTP {e.code}", file=sys.stderr)
            failed = True
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"[FAIL] {url} {e}", file=sys.stderr)
            failed = True

    if failed:
        print("\nERGEBNIS: mindestens eine Route fehlgeschlagen.", file=sys.stderr)
        return 1
    print("\nERGEBNIS: alle geprueften Dashboard-Routen OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
