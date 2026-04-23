#!/usr/bin/env python3
"""
Validiert, dass AMS-Synthetik aehnliche statistische Momente wie historische Extremprofile zeigt.

Aufruf (laufender adversarial-engine, z. B. Port 8145):
  python scripts/validate_ams_moments.py --base-url http://127.0.0.1:8145

Exit-Code 0 bei bestandenen Schwellen, 1 sonst.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description="AMS Momenten-Validierung")
    p.add_argument("--base-url", default="http://127.0.0.1:8145", help="adversarial-engine Basis-URL")
    p.add_argument("--toxicity", type=float, default=0.88)
    p.add_argument("--seq-len", type=int, default=256)
    args = p.parse_args()
    base = str(args.base_url).rstrip("/")

    try:
        ref = _get_json(f"{base}/ams/v1/reference-extreme-profile")
    except urllib.error.URLError as exc:
        print(f"Referenz-Endpoint nicht erreichbar: {exc}", file=sys.stderr)
        return 1

    ref_lr = ref["moments"]["log_return"]
    ref_k = float(ref_lr["kurtosis_excess"])
    ref_s = abs(float(ref_lr["skewness"]))

    try:
        batch = _post_json(
            f"{base}/ams/v1/toxic-batch",
            {
                "symbol": "BTCUSDT",
                "seq_len": int(args.seq_len),
                "toxicity_0_1": float(args.toxicity),
                "batch": 1,
                "return_arrow": False,
            },
        )
    except urllib.error.URLError as exc:
        print(f"toxic-batch nicht erreichbar: {exc}", file=sys.stderr)
        return 1

    syn_lr = batch["moments"]["log_return"]
    syn_k = float(syn_lr["kurtosis_excess"])
    syn_s = abs(float(syn_lr["skewness"]))

    # Synthetik soll Extremereignis-aehnliche Schwerezeichen tragen (nicht trivial normal).
    ok_k = syn_k >= min(0.25, ref_k * 0.35) and syn_k >= 0.15
    ok_s = syn_s >= min(0.08, ref_s * 0.25) or syn_k >= 0.8

    corr = float(batch["moments"].get("price_depth_corr") or 0.0)
    ok_corr = corr >= 0.25

    print(
        json.dumps(
            {
                "reference_log_return": ref_lr,
                "synthetic_log_return": syn_lr,
                "price_depth_corr": corr,
                "checks": {
                    "kurtosis_extreme": ok_k,
                    "skew_or_kurtosis": ok_s or syn_k >= 0.8,
                    "price_depth_correlation": ok_corr,
                },
            },
            indent=2,
        )
    )

    if ok_k and (ok_s or syn_k >= 0.8) and ok_corr:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
