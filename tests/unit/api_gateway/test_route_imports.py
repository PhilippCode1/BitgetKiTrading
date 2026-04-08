from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)


def test_gateway_route_modules_import_cleanly() -> None:
    importlib.import_module("api_gateway.gateway_read_envelope")
    importlib.import_module("api_gateway.routes_alerts_proxy")
    importlib.import_module("api_gateway.routes_live")
    importlib.import_module("api_gateway.routes_live_broker_operator")
    importlib.import_module("api_gateway.routes_live_broker_proxy")
    importlib.import_module("api_gateway.routes_live_broker_safety")
    importlib.import_module("api_gateway.manual_action")
    importlib.import_module("api_gateway.mutation_deps")
    importlib.import_module("api_gateway.routes_monitor_proxy")
    importlib.import_module("api_gateway.operator_health_pdf")
    importlib.import_module("api_gateway.routes_system_health")
    importlib.import_module("api_gateway.routes_llm_operator")
    importlib.import_module("api_gateway.llm_orchestrator_forward")
    importlib.import_module("api_gateway.routes_commerce")
    importlib.import_module("api_gateway.routes_commerce_customer")
    importlib.import_module("api_gateway.routes_commerce_payments")
    importlib.import_module("api_gateway.payments.wise_webhook")
    importlib.import_module("api_gateway.payments.paypal_stub_webhook")
    importlib.import_module("api_gateway.db_payment_failure_log")
    importlib.import_module("api_gateway.contract_pdf")
    importlib.import_module("api_gateway.esign_mock")
    importlib.import_module("api_gateway.db_contract_workflow")
    importlib.import_module("api_gateway.routes_commercial_contracts")
    importlib.import_module("api_gateway.subscription_billing_amounts")
    importlib.import_module("api_gateway.db_subscription_billing")
    importlib.import_module("api_gateway.routes_commerce_subscription_billing")
    importlib.import_module("api_gateway.routes_commerce_profit_fee")
    importlib.import_module("api_gateway.db_profit_fee")
    importlib.import_module("api_gateway.db_settlement")
    importlib.import_module("api_gateway.routes_commerce_settlement")
