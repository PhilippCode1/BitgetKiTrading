from __future__ import annotations

import json
import logging
import time
from typing import Any

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.exceptions import RetryableLLMError
from llm_orchestrator.llm_metrics import (
    add_tokens,
    observe_request_duration,
    record_parsing_error,
)

logger = logging.getLogger("llm_orchestrator.openai")

_RESPONSES_INSTRUCTIONS_DE = (
    "Antworte ausschliesslich mit JSON, das exakt dem vorgegebenen Schema entspricht "
    "(Structured Outputs, strict)."
)
_CHAT_SYSTEM_DE = (
    "Antworte ausschliesslich mit JSON, das exakt dem vorgegebenen Schema entspricht."
)


def _usage_from_chat_completion(comp: Any) -> tuple[int, int]:
    u = getattr(comp, "usage", None)
    if u is None:
        return 0, 0
    p = int(getattr(u, "prompt_tokens", None) or 0)
    c = int(getattr(u, "completion_tokens", None) or 0)
    return p, c


def _usage_from_responses_api(resp: Any) -> tuple[int, int]:
    u = getattr(resp, "usage", None)
    if u is None:
        return 0, 0
    pin = (
        getattr(u, "input_tokens", None)
        or getattr(u, "prompt_tokens", None)
    )
    cout = (
        getattr(u, "output_tokens", None)
        or getattr(u, "completion_tokens", None)
    )
    return int(pin or 0), int(cout or 0)


def _record_openai_call_metrics(
    task_type: str | None,
    duration_sec: float,
    transport: str,
    *,
    comp: Any = None,
    resp: Any = None,
) -> None:
    observe_request_duration(
        duration_sec, "openai", transport, task_type=task_type
    )
    p, t = 0, 0
    if comp is not None:
        p, t = _usage_from_chat_completion(comp)
    elif resp is not None:
        p, t = _usage_from_responses_api(resp)
    if p or t:
        add_tokens(prompt_tokens=p, completion_tokens=t)


def _json_loads_for_metrics(text: str, task_type: str | None) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        record_parsing_error(task_type, "json_decode")
        raise


def _merge_system_layers(extra: str | None, core: str) -> str:
    e = (extra or "").strip()
    if not e:
        return core
    return f"{e}\n\n{core}"


def _append_system_suffix(base: str, append: str | None) -> str:
    a = (append or "").strip()
    if not a:
        return base
    return f"{base}\n\n{a}"


def _openai_client_timeout_sec(settings: LLMOrchestratorSettings) -> float:
    # httpx-Client-Timeout: knapp ueber dem groessten per-Request-Deep-Timeout
    return min(
        60.0,
        max(12.0, float(settings.llm_request_timeout_ms_deep) / 1000.0 + 5.0),
    )


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
        system_instructions_append_de: str | None = None,
        task_type: str | None = None,
    ) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("OpenAI: OPENAI_API_KEY fehlt")
        use_model = (model or "").strip() or self.default_model
        cap_ms = min(
            int(timeout_ms),
            self._settings.llm_request_timeout_ms_deep,
        )
        timeout_s = max(0.1, min(cap_ms, self._settings.llm_timeout_ms) / 1000.0)

        if self.responses_api_usable:
            try:
                return self._generate_via_responses(
                    use_model,
                    schema_json,
                    prompt,
                    temperature,
                    timeout_s,
                    system_instructions_de=system_instructions_de,
                    system_instructions_append_de=system_instructions_append_de,
                    task_type=task_type,
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
                system_instructions_append_de=system_instructions_append_de,
                task_type=task_type,
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
        system_instructions_append_de: str | None = None,
        task_type: str | None,
    ) -> dict[str, Any]:
        assert self._client is not None
        instr = _append_system_suffix(
            _merge_system_layers(
                system_instructions_de,
                _RESPONSES_INSTRUCTIONS_DE,
            ),
            system_instructions_append_de,
        )
        t0 = time.perf_counter()
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
            observe_request_duration(
                time.perf_counter() - t0, "openai", "responses", task_type=task_type
            )
            raise RetryableLLMError(str(exc), status_code=429) from exc
        except APITimeoutError as exc:
            observe_request_duration(
                time.perf_counter() - t0, "openai", "responses", task_type=task_type
            )
            raise RetryableLLMError(str(exc), status_code=504) from exc
        except APIError as exc:
            observe_request_duration(
                time.perf_counter() - t0, "openai", "responses", task_type=task_type
            )
            status = getattr(exc, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                raise RetryableLLMError(str(exc), status_code=status) from exc
            raise
        if getattr(resp, "error", None) is not None:
            _record_openai_call_metrics(
                task_type, time.perf_counter() - t0, "responses", resp=resp
            )
            err = resp.error
            raise RuntimeError(
                f"OpenAI Responses error code={err.code} message={err.message}"
            )
        st = getattr(resp, "status", None)
        if st and st != "completed":
            _record_openai_call_metrics(
                task_type, time.perf_counter() - t0, "responses", resp=resp
            )
            raise RuntimeError(f"OpenAI Responses status={st}")
        text = (resp.output_text or "").strip()
        if not text:
            _record_openai_call_metrics(
                task_type, time.perf_counter() - t0, "responses", resp=resp
            )
            raise RuntimeError("OpenAI Responses: leerer output_text")
        _record_openai_call_metrics(
            task_type, time.perf_counter() - t0, "responses", resp=resp
        )
        logger.info("openai transport=responses model=%s", use_model)
        return _json_loads_for_metrics(text, task_type)

    def _generate_via_chat_json_schema(
        self,
        use_model: str,
        schema_json: dict[str, Any],
        prompt: str,
        temperature: float,
        timeout_s: float,
        *,
        system_instructions_de: str | None,
        system_instructions_append_de: str | None = None,
        task_type: str | None,
    ) -> dict[str, Any]:
        assert self._client is not None
        sys_content = _append_system_suffix(
            _merge_system_layers(
                system_instructions_de,
                _CHAT_SYSTEM_DE,
            ),
            system_instructions_append_de,
        )
        messages = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": prompt},
        ]
        t0 = time.perf_counter()
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
            observe_request_duration(
                time.perf_counter() - t0,
                "openai",
                "chat_completions",
                task_type=task_type,
            )
            raise RetryableLLMError(str(exc), status_code=429) from exc
        except APITimeoutError as exc:
            observe_request_duration(
                time.perf_counter() - t0,
                "openai",
                "chat_completions",
                task_type=task_type,
            )
            raise RetryableLLMError(str(exc), status_code=504) from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                observe_request_duration(
                    time.perf_counter() - t0,
                    "openai",
                    "chat_completions",
                    task_type=task_type,
                )
                raise RetryableLLMError(str(exc), status_code=status) from exc
            if self._settings.llm_openai_allow_chat_fallback:
                logger.info(
                    "OpenAI chat json_schema nicht moeglich (%s), Fallback json_object",
                    exc,
                )
                observe_request_duration(
                    time.perf_counter() - t0,
                    "openai",
                    "chat_completions",
                    task_type=task_type,
                )
                return self._generate_json_object_fallback(
                    use_model,
                    schema_json,
                    prompt,
                    temperature,
                    timeout_s,
                    system_instructions_de=system_instructions_de,
                    system_instructions_append_de=system_instructions_append_de,
                    task_type=task_type,
                )
            observe_request_duration(
                time.perf_counter() - t0,
                "openai",
                "chat_completions",
                task_type=task_type,
            )
            raise

        _record_openai_call_metrics(
            task_type, time.perf_counter() - t0, "chat_completions", comp=comp
        )
        text = comp.choices[0].message.content or "{}"
        logger.info("openai transport=chat_completions model=%s", use_model)
        return _json_loads_for_metrics(text, task_type)

    def _generate_json_object_fallback(
        self,
        use_model: str,
        schema_json: dict[str, Any],
        prompt: str,
        temperature: float,
        timeout_s: float,
        *,
        system_instructions_de: str | None,
        system_instructions_append_de: str | None = None,
        task_type: str | None,
    ) -> dict[str, Any]:
        assert self._client is not None
        user = (
            f"{prompt}\n\nErforderliches JSON-Schema (einhalten):\n"
            f"{json.dumps(schema_json, ensure_ascii=False)}"
        )
        sys_msg = _append_system_suffix(
            _merge_system_layers(
                system_instructions_de,
                "Antworte mit einem einzigen JSON-Objekt.",
            ),
            system_instructions_append_de,
        )
        t0 = time.perf_counter()
        try:
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
        except (RateLimitError, APITimeoutError) as exc:
            observe_request_duration(
                time.perf_counter() - t0,
                "openai",
                "chat_json_object",
                task_type=task_type,
            )
            if isinstance(exc, RateLimitError):
                raise RetryableLLMError(str(exc), status_code=429) from exc
            raise RetryableLLMError(str(exc), status_code=504) from exc
        except APIError as exc:
            observe_request_duration(
                time.perf_counter() - t0,
                "openai",
                "chat_json_object",
                task_type=task_type,
            )
            status = getattr(exc, "status_code", None)
            if status in (429, 500, 502, 503, 504):
                raise RetryableLLMError(str(exc), status_code=status) from exc
            raise
        _record_openai_call_metrics(
            task_type, time.perf_counter() - t0, "chat_json_object", comp=comp
        )
        text = comp.choices[0].message.content or "{}"
        logger.warning("openai transport=chat_json_object_fallback model=%s", use_model)
        return _json_loads_for_metrics(text, task_type)

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
