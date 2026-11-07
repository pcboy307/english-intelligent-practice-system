"""DeepSeek JSON client, retry policy, circuit breaker and CNY cost ledger."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx


class DeepSeekGenerationError(RuntimeError):
    pass


class MissingAPIKey(DeepSeekGenerationError):
    pass


class TransportRetriesExhausted(DeepSeekGenerationError):
    pass


class CircuitOpen(DeepSeekGenerationError):
    pass


class DeepSeekAPIError(DeepSeekGenerationError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"DEEPSEEK_API_ERROR:{status_code}:{message}")
        self.status_code = status_code
        self.message = message


class FinishReasonError(DeepSeekGenerationError):
    def __init__(
        self,
        message: str,
        *,
        raw_content: str = "",
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_content = raw_content
        self.raw_response = raw_response


class ResponseJSONError(DeepSeekGenerationError):
    pass


class BudgetThresholdReached(DeepSeekGenerationError):
    pass


class RepairExhausted(DeepSeekGenerationError):
    def __init__(self, purpose: str, errors: list[str]) -> None:
        super().__init__(
            f"DEEPSEEK_REPAIR_EXHAUSTED:{purpose}:"
            + "; ".join(errors[-3:])
        )
        self.purpose = purpose
        self.errors = errors


@dataclass
class RequestRecord:
    purpose: str
    attempt: int
    status: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_seconds: float = 0.0
    finish_reason: str | None = None
    request_id: str | None = None
    error: str | None = None
    raw_content: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = {
            "purpose": self.purpose,
            "attempt": self.attempt,
            "status": self.status,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "elapsed_seconds": self.elapsed_seconds,
            "finish_reason": self.finish_reason,
            "request_id": self.request_id,
            "error": self.error,
        }
        if self.raw_content is not None:
            result["raw_content"] = self.raw_content
        return result


@dataclass
class DeepSeekResponse:
    data: dict[str, Any]
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_seconds: float
    request_id: str | None


def parse_json_content(content: str) -> dict[str, Any]:
    stripped = content.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        stripped = fenced.group(1).strip()
    value = json.loads(stripped)
    if not isinstance(value, dict):
        raise ValueError("JSON_CONTENT_MUST_BE_AN_OBJECT")
    return value


def select_v41_model_id(models: list[dict[str, Any]]) -> str:
    available = {
        str(item.get("id"))
        for item in models
        if isinstance(item, dict) and item.get("id")
    }
    if "deepseek-flash" in available:
        return "deepseek-flash"
    raise ValueError("DEEPSEEK_V41_MODEL_NOT_FOUND")


class DeepSeekClient:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
        raw_output_dir: str | Path | None = None,
    ) -> None:
        self.config = config
        self.api_key = os.getenv(config["api_key_env"])
        if not self.api_key:
            raise MissingAPIKey(
                f"{config['api_key_env']} is not set in the environment."
            )
        self.http_client = http_client or httpx.Client(timeout=120.0)
        self.sleep = sleep or time.sleep
        self.raw_output_dir = (
            Path(raw_output_dir) if raw_output_dir is not None else None
        )
        self.requests: list[RequestRecord] = []
        self.consecutive_transport_failures = 0

    @property
    def chat_endpoint(self) -> str:
        return self.config["base_url"].rstrip("/") + "/chat/completions"

    @property
    def models_endpoint(self) -> str:
        return self.config["base_url"].rstrip("/") + "/models"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _persist_raw(self, request_id: str | None, content: str) -> None:
        if self.raw_output_dir is None or not request_id:
            return
        self.raw_output_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", request_id)
        (self.raw_output_dir / f"{safe_id}.txt").write_text(
            content[:8000],
            encoding="utf-8",
        )

    def list_models(self) -> list[dict[str, Any]]:
        response = self.http_client.get(
            self.models_endpoint,
            headers=self.headers,
        )
        if response.status_code >= 400:
            self._persist_raw(
                response.headers.get("x-request-id"),
                f"HTTP {response.status_code}\n{response.text}",
            )
            raise DeepSeekAPIError(response.status_code, response.text[:500])
        payload = response.json()
        return list(payload.get("data") or [])

    def ping(self) -> dict[str, Any]:
        model_id = self.config.get("model_id")
        if not model_id:
            raise DeepSeekGenerationError("DEEPSEEK_MODEL_ID_NOT_CONFIGURED")
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": 0,
            "max_tokens": 1,
            "stream": False,
        }
        started = time.perf_counter()
        response = self.http_client.post(
            self.chat_endpoint,
            headers=self.headers,
            json=payload,
        )
        elapsed = time.perf_counter() - started
        if response.status_code >= 400:
            raise DeepSeekAPIError(response.status_code, response.text[:500])
        result = response.json()
        choice = result["choices"][0]
        usage = result.get("usage") or {}
        self.consecutive_transport_failures = 0
        request_id = (
            response.headers.get("x-request-id")
            or result.get("id")
        )
        self.requests.append(
            RequestRecord(
                purpose="ping",
                attempt=1,
                status="ok",
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                elapsed_seconds=elapsed,
                finish_reason=choice.get("finish_reason"),
                request_id=request_id,
            )
        )
        return {
            "model_id": model_id,
            "request_id": request_id,
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "elapsed_seconds": elapsed,
        }

    def chat_json(
        self,
        purpose: str,
        prompt: str,
        *,
        max_tokens: int | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> DeepSeekResponse:
        if self.consecutive_transport_failures >= 5:
            raise CircuitOpen("CIRCUIT_OPEN_AFTER_FIVE_CONSECUTIVE_FAILURES")
        model_id = self.config.get("model_id")
        if not model_id:
            raise DeepSeekGenerationError("DEEPSEEK_MODEL_ID_NOT_CONFIGURED")
        response_format = (
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "generation_batch",
                    "strict": True,
                    "schema": response_schema,
                },
            }
            if response_schema is not None
            else {"type": "json_object"}
        )
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return one valid JSON object only. "
                        "Do not include Markdown fences or commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": float(self.config["temperature"]),
            "max_tokens": int(max_tokens or self.config["max_tokens"]),
            "response_format": response_format,
            "thinking": {"type": "disabled"},
            "stream": False,
        }

        for attempt in range(1, 5):
            started = time.perf_counter()
            try:
                response = self.http_client.post(
                    self.chat_endpoint,
                    headers=self.headers,
                    json=payload,
                )
            except httpx.HTTPError as error:
                record = RequestRecord(
                    purpose=purpose,
                    attempt=attempt,
                    status="transport_error",
                    elapsed_seconds=time.perf_counter() - started,
                    error=str(error),
                )
                self.requests.append(record)
                self.consecutive_transport_failures += 1
                if self.consecutive_transport_failures >= 5:
                    raise CircuitOpen(
                        "CIRCUIT_OPEN_AFTER_FIVE_CONSECUTIVE_FAILURES"
                    ) from error
                if attempt == 4:
                    raise TransportRetriesExhausted(
                        "TRANSPORT_RETRIES_EXHAUSTED"
                    ) from error
                self.sleep(float(2 ** (attempt - 1)))
                continue

            elapsed = time.perf_counter() - started
            if response.status_code == 429 or response.status_code >= 500:
                record = RequestRecord(
                    purpose=purpose,
                    attempt=attempt,
                    status="transport_error",
                    elapsed_seconds=elapsed,
                    error=f"HTTP {response.status_code}",
                )
                self.requests.append(record)
                self.consecutive_transport_failures += 1
                if self.consecutive_transport_failures >= 5:
                    raise CircuitOpen(
                        "CIRCUIT_OPEN_AFTER_FIVE_CONSECUTIVE_FAILURES"
                    )
                if attempt == 4:
                    raise TransportRetriesExhausted(
                        "TRANSPORT_RETRIES_EXHAUSTED"
                    )
                self.self_backoff(attempt)
                continue

            if response.status_code >= 400:
                response_text = response.text
                request_id = response.headers.get("x-request-id")
                try:
                    error_payload = response.json()
                    request_id = request_id or (
                        (error_payload.get("error") or {}).get("request_id")
                    )
                except json.JSONDecodeError:
                    pass
                record = RequestRecord(
                    purpose=purpose,
                    attempt=attempt,
                    status="api_error",
                    elapsed_seconds=elapsed,
                    error=response_text[:500],
                    request_id=request_id,
                )
                self.requests.append(record)
                self._persist_raw(
                    request_id,
                    f"HTTP {response.status_code}\n{response_text}",
                )
                raise DeepSeekAPIError(
                    response.status_code,
                    response_text[:500],
                )

            self.consecutive_transport_failures = 0
            payload_json = response.json()
            choice = payload_json["choices"][0]
            finish_reason = str(choice.get("finish_reason") or "unknown")
            content = choice["message"].get("content") or ""
            usage = payload_json.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            completion_tokens = int(usage.get("completion_tokens", 0))
            request_id = (
                response.headers.get("x-request-id")
                or payload_json.get("id")
            )
            self._persist_raw(request_id, content)
            record = RequestRecord(
                purpose=purpose,
                attempt=attempt,
                status="ok",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                elapsed_seconds=elapsed,
                finish_reason=finish_reason,
                request_id=request_id,
            )
            self.requests.append(record)
            record.raw_content = content
            if finish_reason == "length":
                record.status = "finish_reason_length"
                raise FinishReasonError(
                    "DEEPSEEK_OUTPUT_TRUNCATED_BY_LENGTH",
                    raw_content=content,
                    raw_response=payload_json,
                )
            try:
                data = parse_json_content(content)
            except (json.JSONDecodeError, ValueError) as error:
                record.status = "json_parse_error"
                record.error = str(error)
                raise ResponseJSONError("DEEPSEEK_JSON_PARSE_FAILED") from error
            return DeepSeekResponse(
                data=data,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                elapsed_seconds=elapsed,
                request_id=request_id,
            )

        raise AssertionError("DEEPSEEK_RETRY_LOOP_EXITED")

    def self_backoff(self, attempt: int) -> None:
        self.sleep(float(2 ** (attempt - 1)))


class CostLedger:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.records: list[dict[str, Any]] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def total_cny(self) -> float:
        return (
            self.prompt_tokens
            * float(self.config["price_input_per_1m_cny"])
            / 1_000_000
            + self.completion_tokens
            * float(self.config["price_output_per_1m_cny"])
            / 1_000_000
        )

    def record(
        self,
        *,
        purpose: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        prompt = int(prompt_tokens)
        completion = int(completion_tokens)
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.records.append(
            {
                "purpose": purpose,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
                "cost_cny": (
                    prompt
                    * float(self.config["price_input_per_1m_cny"])
                    / 1_000_000
                    + completion
                    * float(self.config["price_output_per_1m_cny"])
                    / 1_000_000
                ),
            }
        )

    def assert_below_threshold(self, bucket: str) -> None:
        cap = float(self.config["budget_cap_cny"][bucket])
        if self.total_cny >= cap * 0.8:
            raise BudgetThresholdReached(
                f"DEEPSEEK_BUDGET_80_PERCENT_REACHED bucket={bucket} "
                f"cost_cny={self.total_cny:.6f} cap_cny={cap:.2f}"
            )


def run_repair_loop(
    *,
    client: DeepSeekClient,
    ledger: CostLedger,
    purpose: str,
    prompt: str,
    validate: Callable[[dict[str, Any]], Any],
    max_repair_retries: int = 3,
    response_schema: dict[str, Any] | None = None,
) -> Any:
    errors: list[str] = []
    for repair_attempt in range(max_repair_retries + 1):
        repair_prompt = prompt
        if errors:
            repair_prompt += (
                "\n\nThe previous response was rejected. Fix these exact errors "
                "and return the complete JSON object again:\n"
                + json.dumps(errors, ensure_ascii=False, indent=2)
            )
        try:
                response = client.chat_json(
                    purpose,
                    repair_prompt,
                    response_schema=response_schema,
                )
        except (FinishReasonError, ResponseJSONError) as error:
            request_record = client.requests[-1] if client.requests else None
            if request_record is not None:
                ledger.record(
                    purpose=purpose,
                    prompt_tokens=request_record.prompt_tokens,
                    completion_tokens=request_record.completion_tokens,
                )
                if "budget_cap_cny" in ledger.config:
                    ledger.assert_below_threshold("pilot")
            errors.append(str(error))
            continue
        ledger.record(
            purpose=purpose,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
        if "budget_cap_cny" in ledger.config:
            ledger.assert_below_threshold("pilot")
        try:
            return validate(response.data)
        except (KeyError, TypeError, ValueError) as error:
            requests = getattr(client, "requests", [])
            if requests:
                requests[-1].status = "validation_error"
                requests[-1].error = str(error)
            errors.append(str(error))
    raise RepairExhausted(purpose, errors)
