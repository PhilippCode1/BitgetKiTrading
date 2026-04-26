from __future__ import annotations

from scripts.dr_postgres_restore_test import secret_surface_issues as restore_secret_surface_issues
from tools.verify_alert_routing import secret_surface_issues as alert_secret_surface_issues


def test_secret_like_values_must_be_redacted() -> None:
    restore_issues = restore_secret_surface_issues(
        {"database_url": "postgresql://user:secret@host:5432/db"}
    )
    assert "secret_like_field_not_redacted:database_url" in restore_issues

    alert_issues = alert_secret_surface_issues(
        {"authorization": "Bearer super-secret-token"}
    )
    assert "secret_like_field_not_redacted:authorization" in alert_issues


def test_redacted_values_pass_secret_surface_checks() -> None:
    assert restore_secret_surface_issues({"database_url": "[REDACTED]"}) == []
    assert alert_secret_surface_issues({"authorization": "[REDACTED]"}) == []
