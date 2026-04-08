"""Gateway-Konfiguration (ENV via pydantic, zentral in ``config.gateway_settings``)."""

from __future__ import annotations

from config.gateway_settings import GatewaySettings, get_gateway_settings

__all__ = ["GatewaySettings", "get_gateway_settings"]
