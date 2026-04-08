# Tests (Monorepo)

- **Unit**: `tests/unit/<komponente>/` — ohne Docker.
- **Integration**: `tests/integration/` und Marker `@pytest.mark.integration`.
- **Weitere Suites**: `tests/signal_engine`, `tests/paper_broker`, `tests/learning_engine`, …
- **Konfiguration**: Root `pyproject.toml` (`pytest`, `coverage`), `tests/conftest.py` (PYTHONPATH).

```bash
pytest tests shared/python/tests -m "not integration"
```

Details: `docs/testing_guidelines.md`.
