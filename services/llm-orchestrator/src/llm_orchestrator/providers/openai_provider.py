from __future__ import annotations

import json
import logging
from typing import Any

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.exceptions import RetryableLLMError

logger = logging.getLogger("llm_orchestrator.openai")

_RESPONSES_INSTRUCTIONS_DE = (
    "Antworte ausschliesslich mit JSON, das exakt dem vorgegebenen Schema entspricht "
    "(Structured Outputs, strict)."
)
_CHAT_SYSTEM_DE = (
    "Antworte ausschliesslich mit JSON, das exakt dem vorgegebenen Schema entspricht."
)


def _merge_system_layers(extra: str | None, core: str) -> str:
    e = (extra or "").strip()
    if not e:
        return core
    return f"{e}\n\n{core}"


def _openai_client_timeout_sec(settings: LLMOrchestratorSettings) -> float:
    return max(120.0, settings.llm_timeout_ms / 1000.0)


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, settings: LLMOrchestratorSettings) -> None:
        self._settings = settings
        key = (settings.openai_api_key or "").strip()
        self._client = OpenAI(
            api_key=key or None, timeout=_openai_client_timeout_sec(settings)
        )
        self.default_model = settings.openai_model_primary
        self._has_responses = hasattr(self._client, "responses")

    @property
    def available(self) -> bool:
        return bool((self._settings.openai_api_key or "").strip())

    @property
    def sdk_has_responses(self) -> bool:
        return self._has_responses

    @property
    def responses_api_usable(self) -> bool:
        return bool(
            self._settings.llm_openai_use_responses_api
            and self._has_responses
            and self.available
        )

    def structured_transport_hint(self) -> str:
        if not self.available:
            return "unavailable"
        if self.responses_api_usable:
            return "responses"
        return "chat_completions"

    def generate_structured(
        self,
        schema_json: dict[str, Any],
        prompt: str,
        *,
        temperature: float,
        timeout_ms: int,
        model: str | None = None,
        system_instructions_de: str | None = None,
    ) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("OpenAI: OPENAI_API_KEY fehlt")
        use_model = (model or "").strip() or self.default_model
        timeout_s = max(1.0, timeout_ms / 1000.0)

        if self.responses_api_usable:
            try:
                return self._generate_via_responses(
                    use_model,
                    schema_json,
                    prompt,
                    temperature,
                    timeout_s,
                    system_instructions_de=system_instructions_de,
                )
            except Exception as exc:
                if not self._settings.llm_openai_allow_chat_fallback:
                    raise self._map_api_error(exc, transport="responses") from exc
                logger.warning(
                    "OpenAI Responses fehlgeschlagen (%s), Chat-Fallback aktiv",
                    exc,
                )
        elif self._settings.llm_openai_use_responses_api and not self._has_responses:
            logger.warning(
                "OpenAI SDK ohne responses-Resource — Chat Completions (json_schema). "
                "SDK auf openai>=2.8 empfohlen."
            )

        try:
            return self._generate_via_chat_json_schema(
                use_model,
                schema_json,
                prompt,
                temperature,
                timeout_s,
                system_instructions_de=system_instructions_de,
            )
        except APIError as exc:
            raise self._map_api_error(exc, transport="chat_completions") from exc

    def _generate_via_responses(
        self,
        use_model: str,
        schema_json: dict[str, Any],
        prompt: str,
        temperature: float,
        timeout_s: float,
        *,
        system_instructions_de: str | None,
    ) -> dict[str, Any]:
        assert self._client is not None
        instr = _merge_system_layers(
            system_instructions_de,
            _RESPONSES_INSTRUCTIONS_DE,
        )
        try:
            resp = self._client.responses.create(
                model=use_model,
                instructions=instr,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "structured_output",
                        "strict": True,
                        "schema": schema_json,
                    }
                },
                temperature=temperature,
                timeout=timeout_s,
            )
        except RateLimitError as exc:
            raise RetryableLLMError(str(exc), status_code=429) from exc
        except APITimeoutError as exc:
            raise RetryableLLMError(str(exc), status_code=504) from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                raise RetryableLLMError(str(exc), status_code=status) from exc
            raise
        if getattr(resp, "error", None) is not None:
            err = resp.error
            raise RuntimeError(
                f"OpenAI Responses error code={err.code} message={err.message}"
            )
        st = getattr(resp, "status", None)
        if st and st != "completed":
            raise RuntimeError(f"OpenAI Responses status={st}")
        text = (resp.output_text or "").strip()
        if not text:
            raise RuntimeError("OpenAI Responses: leerer output_text")
        logger.info("openai transport=responses model=%s", use_model)
        return json.loads(text)

    def _generate_via_chat_json_schema(
        self,
        use_model: str,
        schema_json: dict[str, Any],
        prompt: str,
        temperature: float,
        timeout_s: float,
        *,
        system_instructions_de: str | None,
    ) -> dict[str, Any]:
        assert self._client is not None
        sys_content = _merge_system_layers(
            system_instructions_de,
            _CHAT_SYSTEM_DE,
        )
        messages = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": prompt},
        ]
        try:
            comp = self._client.chat.completions.create(
                model=use_model,
                messages=messages,
                temperature=temperature,
                timeout=timeout_s,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "strict": True,
                        "schema": schema_json,
                    },
                },
            )
        except RateLimitError as exc:
            raise RetryableLLMError(str(exc), status_code=429) from exc
        except APITimeoutError as exc:
            raise RetryableLLMError(str(exc), status_code=504) from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                raise RetryableLLMError(str(exc), status_code=status) from exc
            if self._settings.llm_openai_allow_chat_fallback:
                logger.info(
                    "OpenAI chat json_schema nicht moeglich (%s), Fallback json_object",
                    exc,
                )
                return self._generate_json_object_fallback(
                    use_model,
                    schema_json,
                    prompt,
                    temperature,
                    timeout_s,
                    system_instructions_de=system_instructions_de,
                )
            raise

        text = comp.choices[0].message.content or "{}"
        logger.info("openai transport=chat_completions model=%s", use_model)
        return json.loads(text)

    def _generate_json_object_fallback(
        self,
        use_model: str,
        schema_json: dict[str, Any],
        prompt: str,
        temperature: float,
        timeout_s: float,
        *,
        system_instructions_de: str | None,
    ) -> dict[str, Any]:
        assert self._client is not None
        user = (
            f"{prompt}\n\nErforderliches JSON-Schema (einhalten):\n"
            f"{json.dumps(schema_json, ensure_ascii=False)}"
        )
        sys_msg = _merge_system_layers(
            system_instructions_de,
            "Antworte mit einem einzigen JSON-Objekt.",
        )
        comp = self._client.chat.completions.create(
            model=use_model,
            messages=[
                {
                    "role": "system",
                    "content": sys_msg,
                },
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            timeout=timeout_s,
            response_format={"type": "json_object"},
        )
        text = comp.choices[0].message.content or "{}"
        logger.warning("openai transport=chat_json_object_fallback model=%s", use_model)
        return json.loads(text)

    def _map_api_error(self, exc: BaseException, *, transport: str) -> BaseException:
        if isinstance(exc, RateLimitError):
            return RetryableLLMError(f"{transport}:{exc}", status_code=429)
        if isinstance(exc, APITimeoutError):
            return RetryableLLMError(f"{transport}:{exc}", status_code=504)
        if isinstance(exc, APIError):
            status = getattr(exc, "status_code", None)
            rid = getattr(exc, "request_id", None)
            body = f"{transport}:status={status} request_id={rid} {exc}"
            if status in (429, 500, 502, 503, 504):
                return RetryableLLMError(body, status_code=status)
            return RuntimeError(body)
        if isinstance(exc, json.JSONDecodeError):
            return RuntimeError(f"{transport}:json_decode:{exc}")
        return RuntimeError(f"{transport}:{exc}")
