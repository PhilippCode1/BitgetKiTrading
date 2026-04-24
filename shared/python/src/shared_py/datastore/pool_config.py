# Prompt 35: zentrale Pool-Parameter (API-Gateway, live-broker, ggf. weitere Services)
SQLALCHEMY_POOL_SIZE: int = 20
SQLALCHEMY_MAX_OVERFLOW: int = 10
SQLALCHEMY_POOL_RECYCLE_SEC: int = 3600
# sichtbar gleichzusetzen: pool_size + max_overflow = max. gleichzeitige DB-Verbindungen pro Prozess
PSYCOPG_POOL_MAX_SIZE: int = SQLALCHEMY_POOL_SIZE + SQLALCHEMY_MAX_OVERFLOW
PSYCOPG_POOL_MAX_LIFETIME_SEC: int = 3600
