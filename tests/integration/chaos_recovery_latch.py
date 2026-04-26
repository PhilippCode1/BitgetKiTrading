"""
Prompt 72: Redis-Chaos + global_halt — kein „Self-Healing“ Live-Modus ohne Operator-Quittung.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import redis

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
_SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for _p in (str(LIVE_BROKER_SRC), str(_SHARED_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from live_broker.config import LiveBrokerSettings
from live_broker.exceptions import GlobalHaltException
from live_broker.global_halt_latch import GlobalHaltLatch, publish_global_halt_state
from live_broker.orders.service import LiveBrokerOrderService
from live_broker.persistence.repo import LiveBrokerRepository
from shared_py.chaos.grpc_chaos import build_timesfm_chaos_interceptors
from shared_py.chaos.infra_chaos import wrap_redis_with_chaos_latency
from shared_py.shadow_live_divergence import get_shadow_match_latch_read_status

pytestmark = [pytest.mark.integration, pytest.mark.stack_recovery, pytest.mark.chaos]


def _ru() -> str:
    u = (os.getenv("TEST_REDIS_URL") or os.getenv("REDIS_URL") or "").strip()
    if not u:
        pytest.skip("TEST_REDIS_URL nicht gesetzt")
    try:
        r = redis.Redis.from_url(u, socket_connect_timeout=1.0, socket_timeout=1.0)
        r.ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Redis nicht erreichbar: {exc}")
    return u


def _dsn() -> str:
    d = (os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not d:
        pytest.skip("TEST_DATABASE_URL nicht gesetzt")
    return d


def test_chaos_redis_tenth_call_adds_latency_over_socket_timeout() -> None:
    """Jeder 10. Aufruf: 6s Verzögerung — mit engem socket_timeout führt das zu harten Fehlern."""
    u = _ru()
    c = redis.Redis.from_url(
        u, decode_responses=True, socket_connect_timeout=1.0, socket_timeout=0.3
    )
    wrap_redis_with_chaos_latency(c, every_n=10, delay_sec=6.0)
    for _i in range(1, 9):
        assert c.ping() is True
    with pytest.raises(redis.exceptions.TimeoutError):
        c.ping()
    c.close()


def test_global_halt_persists_until_operator_clears_after_simulated_chaos(  # noqa: D401
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Axiom: Wenn Halt einmal (z. B. aus Infrastruktur-Desaster) aktiv ist, bleibt
    `system:global_halt` gesetzt, bis ein expliziter Operator-Clear (publish False) erfolgt
    — kein stilles Auto-Reset durch erneute Redis-Verbindung.
    """
    u = _ru()
    dsn = _dsn()
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", dsn),
        ("REDIS_URL", u),
        ("LIVE_BROKER_REQUIRE_COMMERCIAL_GATES", "false"),
    ):
        monkeypatch.setenv(k, v)
    publish_global_halt_state(u, False)
    latch1 = GlobalHaltLatch(u)
    latch1.start()
    time.sleep(0.12)
    try:
        publish_global_halt_state(u, True)
        for _ in range(100):
            if latch1.is_halted:
                break
            time.sleep(0.02)
        assert latch1.is_halted
        r = redis.Redis.from_url(
            u, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        assert r.get("system:global_halt") in ("1", "true", "True", "halt")
    finally:
        try:
            latch1.stop()
        except Exception:  # noqa: BLE001
            pass
    # „Neustart“ / neuer Latch: Zustand kommt erneut aus Redis
    latch2 = GlobalHaltLatch(u)
    latch2.start()
    time.sleep(0.15)
    try:
        assert latch2.is_halted
    finally:
        try:
            latch2.stop()
        except Exception:  # noqa: BLE001
            pass
    publish_global_halt_state(u, False)
    latch3 = GlobalHaltLatch(u)
    latch3.start()
    time.sleep(0.12)
    try:
        for _ in range(80):
            if not latch3.is_halted:
                break
            time.sleep(0.02)
        assert not latch3.is_halted
    finally:
        try:
            latch3.stop()
        except Exception:  # noqa: BLE001
            pass


def test_order_mutation_rejected_on_global_halt(  # noqa: D103
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = _ru()
    dsn = _dsn()
    for k, v in (
        ("REDIS_URL", u),
        ("DATABASE_URL", dsn),
        ("LIVE_BROKER_REQUIRE_COMMERCIAL_GATES", "false"),
        ("BITGET_API_KEY", "k"),
        ("BITGET_API_SECRET", "s"),
        ("BITGET_API_PASSPHRASE", "p"),
    ):
        monkeypatch.setenv(k, v)
    settings = LiveBrokerSettings()
    if not (settings.redis_url or "").strip():
        pytest.skip("LIVE_BROKER REDIS_URL fehlt")
    publish_global_halt_state(u, True)
    latch = GlobalHaltLatch(u)
    latch.start()
    time.sleep(0.1)
    try:
        repo = LiveBrokerRepository(dsn)
        ex = MagicMock()
        ex.place_order = MagicMock(side_effect=RuntimeError("exchange"))
        svc = LiveBrokerOrderService(
            settings,
            repo,
            ex,
            bus=None,
            global_halt=latch,
        )
        for _ in range(40):
            if latch.is_halted:
                break
            time.sleep(0.02)
        assert latch.is_halted
        with pytest.raises(GlobalHaltException):
            svc._call_private(  # noqa: SLF001
                internal_order_id=str(uuid.uuid4()),
                action="create",
                request_path="/x",
                request_json={"a": 1},
                call=lambda: None,
                client_oid="co-1",
                exchange_order_id=None,
            )
    finally:
        publish_global_halt_state(u, False)
        latch.stop()


def test_docker_stop_redis_optional_clears_only_via_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Optional: CHAOS_REDIS_CONTAINER=… — Container stoppt, startet; Halt-Key muss
    manuell quittiert werden (publish False), nicht stillschweigend.
    """
    cname = (os.getenv("CHAOS_REDIS_CONTAINER") or "").strip()
    u = (os.getenv("TEST_REDIS_URL") or "").strip()
    if not cname or not u:
        pytest.skip("CHAOS_REDIS_CONTAINER / TEST_REDIS_URL fuer Docker-Chaos optional")
    if not shutil.which("docker"):
        pytest.skip("docker nicht im PATH")
    r0 = redis.Redis.from_url(u, socket_connect_timeout=1, socket_timeout=1)
    r0.ping()
    r0.set("chaos:prestop", "1", ex=60)
    publish_global_halt_state(u, True)
    time.sleep(0.05)
    try:
        subprocess.run(
            ["docker", "stop", cname], check=True, timeout=90, capture_output=True
        )
    except (subprocess.CalledProcessError, OSError) as e:
        pytest.skip(f"docker stop fehlgeschlagen: {e}")
    time.sleep(1.0)
    with pytest.raises(
        (redis.exceptions.ConnectionError, redis.exceptions.RedisError, OSError)
    ):
        redis.Redis.from_url(
            u, socket_connect_timeout=0.3, socket_timeout=0.3
        ).ping()
    try:
        subprocess.run(
            ["docker", "start", cname], check=True, timeout=90, capture_output=True
        )
    except (subprocess.CalledProcessError, OSError) as e:
        publish_global_halt_state(u, False)
        pytest.fail(f"docker start fehlgeschlagen: {e}")
    deadline = time.monotonic() + 40.0
    while time.monotonic() < deadline:
        try:
            rc = redis.Redis.from_url(u, socket_connect_timeout=2, socket_timeout=2)
            rc.ping()
            if rc.get("system:global_halt") in ("1", "true", "True", "halt", "HALT"):
                break
        except (redis.exceptions.ConnectionError, OSError, redis.exceptions.RedisError):
            time.sleep(0.4)
    r1 = redis.Redis.from_url(
        u, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )
    for _ in range(40):
        try:
            r1.ping()
            break
        except (OSError, redis.exceptions.RedisError):
            time.sleep(0.5)
    v = r1.get("system:global_halt")
    if v in (None, ""):
        publish_global_halt_state(u, False)
        pytest.skip("global_halt-Key nach Redis-Restart weg (ohne persistiertes RDB/AOF)")
    assert str(v).strip() not in ("0", "false", "False", "")
    publish_global_halt_state(u, False)
    v2 = r1.get("system:global_halt")
    assert str(v2 or "0").strip().lower() in ("0", "false", "")


def test_docker_stops_redis_during_signal_loop_read_status_unavailable(  # noqa: D103
) -> None:
    """
    DoD Prompt 72: während laufendem ``ping``-„Signal“-Thread Docker-``stop``,
    danach ``get_shadow_match_latch_read_status`` = ``redis_unavailable``;
    nach Wiederanlauf kein stiller Auto-Live-Modus ohne explizite Quittung.
    """
    cname = (os.getenv("CHAOS_REDIS_CONTAINER") or "").strip()
    u = (os.getenv("TEST_REDIS_URL") or "").strip()
    if not cname or not u or not shutil.which("docker"):
        pytest.skip("CHAOS_REDIS_CONTAINER, TEST_REDIS_URL, docker erforderlich")
    publish_global_halt_state(u, False)
    r0 = redis.Redis.from_url(
        u, socket_connect_timeout=2, socket_timeout=2, decode_responses=True
    )
    r0.ping()
    eid = f"chaos-sig-{uuid.uuid4().hex[:8]}"
    ev = threading.Event()

    def _signal_workload() -> None:
        c = redis.Redis.from_url(
            u, socket_connect_timeout=0.4, socket_timeout=0.4, decode_responses=True
        )
        while not ev.is_set():
            try:
                c.ping()
                time.sleep(0.012)
            except (OSError, redis.exceptions.RedisError) as e:
                err_msg = (str(e) or "").lower()
                if "refused" in err_msg or "time" in err_msg or "closed" in err_msg:
                    return
                return
        return

    th = threading.Thread(target=_signal_workload, name="chaos-signal", daemon=True)
    th.start()
    time.sleep(0.2)
    try:
        subprocess.run(
            ["docker", "stop", cname], check=True, timeout=90, capture_output=True
        )
    except (subprocess.CalledProcessError, OSError) as e:
        ev.set()
        th.join(timeout=5.0)
        pytest.skip(f"docker stop: {e}")
    th.join(timeout=25.0)
    st = "absent"
    for _ in range(15):
        st = get_shadow_match_latch_read_status(u, eid)
        if st == "redis_unavailable":
            break
        time.sleep(0.2)
    try:
        subprocess.run(
            ["docker", "start", cname], check=True, timeout=90, capture_output=True
        )
    except (subprocess.CalledProcessError, OSError) as e:  # noqa: BLE001
        publish_global_halt_state(u, False)
        raise AssertionError(f"docker start fehlgeschlagen: {e}") from e
    deadline = time.monotonic() + 45.0
    r_up: redis.Redis | None = None
    while time.monotonic() < deadline:
        try:
            r_up = redis.Redis.from_url(
                u, socket_connect_timeout=2, socket_timeout=2, decode_responses=True
            )
            r_up.ping()
            break
        except (OSError, redis.exceptions.RedisError):
            time.sleep(0.35)
    if r_up is None:
        publish_global_halt_state(u, False)
        pytest.fail("Redis nach Start nicht erreichbar")
    assert st == "redis_unavailable", f"erwartet redis_unavailable, got {st!r}"
    raw_gh = r_up.get("system:global_halt")
    gh = (str(raw_gh) if raw_gh is not None else "").strip().lower()
    assert gh in ("", "0", "false", "off", "ok")
    latch = GlobalHaltLatch(u)
    latch.start()
    time.sleep(0.15)
    try:
        for _ in range(40):
            if not latch.is_halted:
                break
            time.sleep(0.02)
        assert not latch.is_halted
    finally:
        latch.stop()
    publish_global_halt_state(u, False)


def test_grpc_chaos_interceptor_built() -> None:
    xs = build_timesfm_chaos_interceptors(every_n=10, delay_sec=6.0)
    assert len(xs) == 1

