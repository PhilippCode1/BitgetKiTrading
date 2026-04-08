"""
Kommerzieller Vertragsworkflow (Modul Mate) — Prompt 12.

Persistenz in Postgres (Migration 608); PDF-Erzeugung und E-Sign-Adapter im API-Gateway.
"""

from __future__ import annotations

from enum import Enum

CONTRACT_WORKFLOW_MODULE_VERSION = "1.0.1"
DEFAULT_CONTRACT_TEMPLATE_KEY = "modul_mate_standard_v1"


class TenantContractStatus(str, Enum):
    AWAITING_CUSTOMER_SIGN = "awaiting_customer_sign"
    AWAITING_PROVIDER_SIGN = "awaiting_provider_sign"
    SIGNED_AWAITING_ADMIN = "signed_awaiting_admin"
    ADMIN_REVIEW_COMPLETE = "admin_review_complete"
    VOID = "void"


class ContractDocumentKind(str, Enum):
    DRAFT_PDF = "draft_pdf"
    SIGNED_PDF = "signed_pdf"


class ContractReviewQueueStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    NEEDS_CUSTOMER_INFO = "needs_customer_info"
    APPROVED_CONTRACT = "approved_contract"
    REJECTED = "rejected"
    CLOSED = "closed"


def contract_workflow_descriptor() -> dict[str, str | bool]:
    return {
        "commercial_contract_workflow_module_version": CONTRACT_WORKFLOW_MODULE_VERSION,
        "default_template_key": DEFAULT_CONTRACT_TEMPLATE_KEY,
    }
