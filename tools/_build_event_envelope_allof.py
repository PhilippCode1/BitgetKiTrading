"""event_envelope.schema.json aus Katalog-Map: allOf + if/then fuer Payload-Refs."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sc = root / "shared" / "contracts" / "schemas"
    map_path = root / "shared" / "contracts" / "catalog" / "payload_schema_map.json"
    m: dict[str, str] = json.loads(map_path.read_text(encoding="utf-8"))
    env_path = sc / "event_envelope.schema.json"
    raw: dict = json.loads(env_path.read_text(encoding="utf-8"))
    if (
        "allOf" in raw
        and isinstance(raw["allOf"], list)
        and len(raw["allOf"]) > 0
    ):
        new_base = json.loads(json.dumps(raw["allOf"][0]))  # deep copy
    else:
        new_base = {k: v for k, v in raw.items() if k not in ("$schema", "$id")}
    title = raw.get("title", "EventEnvelope")
    description = raw.get("description", "")
    props: dict = dict(new_base.get("properties", {}))
    props["payload"] = True
    new_base["properties"] = props

    if_thens: list[dict] = []
    for ev, fn in sorted(m.items(), key=lambda x: x[0]):
        ref = f"https://bitget-btc-ai.local/schemas/{fn}"
        if_thens.append(
            {
                "if": {
                    "type": "object",
                    "required": ["event_type"],
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "const": ev,
                        }
                    },
                },
                "then": {
                    "type": "object",
                    "properties": {
                        "payload": {
                            "$ref": ref,
                        }
                    },
                },
            }
        )
    out: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://bitget-btc-ai.local/schemas/event_envelope.schema.json",
        "title": title,
        "description": description,
        "allOf": [new_base, *if_thens],
    }
    env_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("Wrote", env_path)


if __name__ == "__main__":
    main()
