from __future__ import annotations

import uuid

# Stabiler Namespace fuer deterministische parent_id-Keys
DRAWING_PARENT_NAMESPACE = uuid.UUID("018d4a20-1234-7d00-8000-00000000d001")


def stable_parent_id(*parts: str) -> str:
    key = ":".join(parts)
    return str(uuid.uuid5(DRAWING_PARENT_NAMESPACE, key))
