from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
import time
from typing import Any, Callable

from google import genai
from google.genai import types
import requests

from .image_utils import normalize_for_gemma
from .key_pool import ApiKeyPool, KeyUnavailableError
from .prompts import ANNOTATE_CROP_PROMPT, CROP_CLASSIFICATION_PROMPT
from .schemas import GeminiDefectResponse, ModelInfo
from .utils import safe_json_loads

MODEL_PRIORITY = ["gemini-3.8-flash", "gemma-4-26b-a4b-it"]

MODEL_ALIAS = {
    "gemma-4": "gemma-4-26b-a4b-it",
}

DEFAULT_MODEL_NAME = "gemini-3.8-flash"


class GeneratedJSON(dict):
    """Dict-compatible result carrying the model that actually answered."""

    def __init__(self, values: dict[str, Any], model_used: str):
        super().__init__(values)
        self.model_used = model_used


@dataclass
class GeminiService:
    api_keys: list[str]
    request_timeout_sec: int = 45
    key_pool: ApiKeyPool = field(init=False)

    def __post_init__(self) -> None:
        self.key_pool = ApiKeyPool(keys=self.api_keys)
        self._clients: dict[tuple[str, int], genai.Client] = {}
        # Keep a slow or sleeping upstream from pinning an inspection for minutes.
        self.request_timeout_sec = min(max(1, int(self.request_timeout_sec)), 20)

    def _client_for_key(self, key: str, timeout_sec: float | None = None) -> genai.Client:
        timeout_ms = max(1, int((timeout_sec or self.request_timeout_sec) * 1000))
        cache_key = (key, timeout_ms)
        client = self._clients.get(cache_key)
        if client is None:
            client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(timeout=timeout_ms),
            )
            self._clients[cache_key] = client
        return client

    def _with_retry(self, operation: Callable[[genai.Client], Any], max_attempts: int | None = None, timeout_sec: float | None = None) -> Any:
        # Try the configured keys and leave one retry after a short cooldown.
        # Long waits and repeated timeouts made an inspection appear frozen.
        attempts = max_attempts if max_attempts is not None else max(2, len(self.api_keys) + 1)
        last_error: Exception | None = None
        waited_for_cooldown = False

        attempt = 0
        while attempt < attempts:
            try:
                slot = self.key_pool.acquire()
            except KeyUnavailableError as exc:
                wait_seconds = self.key_pool.next_available_in_seconds()
                if wait_seconds != float("inf") and wait_seconds <= 5 and not waited_for_cooldown:
                    time.sleep(wait_seconds + 0.1)
                    waited_for_cooldown = True
                    continue
                if wait_seconds != float("inf"):
                    raise RuntimeError(
                        f"Gemini API key is cooling down. Retry in about {max(1, round(wait_seconds))} seconds."
                    ) from exc
                raise RuntimeError(
                    "No valid Gemini API key is available. Check that your key is valid and its quota is available."
                ) from exc

            attempt += 1
            client = self._client_for_key(slot.key, timeout_sec) if timeout_sec is not None else self._client_for_key(slot.key)
            try:
                result = operation(client)
                self.key_pool.report_success(slot)
                return result
            except Exception as exc:
                self.key_pool.report_failure(slot, exc)
                last_error = exc
                message = str(exc).upper()
                error_kind = ApiKeyPool._classify_error(message)
                if error_kind == "rate_limit":
                    raise RuntimeError(
                        "Gemini API rate limit reached. Wait for the key's quota window to reset, then retry."
                    ) from exc
                is_temporary_server_error = any(
                    marker in message
                    for marker in ("500", "502", "503", "504", "INTERNAL", "DEADLINE_EXCEEDED", "TIMED OUT")
                )
                # An invalid entry should not prevent trying the remaining keys.
                if error_kind != "invalid" and error_kind != "rate_limit" and not is_temporary_server_error:
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("Gemini operation failed without specific error")

    def list_generate_models(self) -> list[ModelInfo]:
        discovered: dict[str, ModelInfo] = {}

        def _list_once(client: genai.Client) -> list[ModelInfo]:
            models: list[ModelInfo] = []
            for model in client.models.list():
                raw_name = getattr(model, "name", "") or ""
                name = raw_name.replace("models/", "")
                if not name:
                    continue

                actions = list(getattr(model, "supported_actions", []) or [])
                if actions and "generateContent" not in actions:
                    continue

                models.append(
                    ModelInfo(
                        name=name,
                        display_name=getattr(model, "display_name", None),
                        supported_actions=actions,
                    )
                )
            return models

        # Probe each key once to avoid missing models due per-key entitlement differences.
        attempts = max(1, len(self.api_keys))
        for _ in range(attempts):
            try:
                partial = self._with_retry(_list_once, max_attempts=1)
            except Exception:
                continue
            for item in partial:
                discovered[item.name] = item

        if not discovered:
            raise RuntimeError("Could not list Gemini models from any configured API key")

        return sorted(discovered.values(), key=lambda m: m.name)

    @staticmethod
    def resolve_model_name(model_name: str | None) -> str | None:
        if not model_name:
            return None
        return MODEL_ALIAS.get(model_name, model_name)

    @staticmethod
    def pick_recommended_model(
        available: list[ModelInfo],
        default_model: str | None = None,
    ) -> str:
        names = {m.name for m in available}
        resolved_default = GeminiService.resolve_model_name(default_model)
        if resolved_default and resolved_default in names:
            return resolved_default

        for candidate in MODEL_PRIORITY:
            resolved_candidate = GeminiService.resolve_model_name(candidate)
            if resolved_candidate in names:
                return resolved_candidate

        if available:
            return available[0].name

        return DEFAULT_MODEL_NAME

    # Gemma models on the Gemini API reject image input (400 INVALID_ARGUMENT), so any call
    # that carries an image goes to a Gemini vision model. Override with VISION_MODELS in .env
    # (comma-separated, tried in order). The first one that works is remembered.
    VISION_MODEL_DEFAULTS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest"]

    def _discover_vision_models(self) -> list[str]:
        """Ask the API which Gemini Flash models this key can use; newest first, non-lite first."""
        import re
        cached = getattr(self, "_discovered_vision", None)
        if cached is not None:
            return cached
        found: list[tuple[float, int, str]] = []
        try:
            for info in self.list_generate_models():
                m = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash(-lite)?", info.name)
                if m:
                    found.append((-float(m.group(1)), 1 if m.group(2) else 0, info.name))
        except Exception as exc:
            print(f"[vision model discovery failed] {str(exc)[:200]!r}", flush=True)
        found.sort()
        names = [n for _, _, n in found][:4]
        print(f"[vision models available for this key] {names}", flush=True)
        self._discovered_vision = names
        return names

    def _vision_candidates(self) -> list[str]:
        import os
        raw = os.getenv("VISION_MODELS", "")
        configured = [m.strip() for m in raw.split(",") if m.strip()]
        candidates = configured + (self._discover_vision_models() if not configured else []) + self.VISION_MODEL_DEFAULTS
        seen: set[str] = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]
        good = getattr(self, "_vision_ok", None)
        if good in candidates:
            candidates.remove(good)
            candidates.insert(0, good)
        return candidates

    def generate_json(self, *, model: str, image_parts: list[tuple[bytes, str]] | None = None, request_timeout_sec: float | None = None, deadline_monotonic: float | None = None, max_attempts: int | None = None, **kwargs: Any) -> dict[str, Any]:
        if not image_parts:
            return self._generate_json_impl(model=model, image_parts=None, request_timeout_sec=request_timeout_sec, deadline_monotonic=deadline_monotonic, max_attempts=max_attempts, **kwargs)
        last_exc: Exception | None = None
        tried: list[str] = []
        candidates = self._vision_candidates()
        for candidate in candidates:
            try:
                result = self._generate_json_impl(model=candidate, image_parts=image_parts, request_timeout_sec=request_timeout_sec, deadline_monotonic=deadline_monotonic, max_attempts=max_attempts, **kwargs)
                self._vision_ok = candidate
                return result
            except RuntimeError as exc:
                text = str(exc).upper()
                if "NO VALID GEMINI API KEY" in text:
                    raise
                print(f"[vision model {candidate!r} failed, trying next] {str(exc)[:200]!r}", flush=True)
                tried.append(f"{candidate}: {str(exc)[-160:]}")
                last_exc = exc
        raise RuntimeError("No vision-capable model worked. Tried -> " + " | ".join(tried)) from last_exc

    def _generate_json_impl(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: dict[str, Any],
        temperature: float,
        max_output_tokens: int,
        image_parts: list[tuple[bytes, str]] | None = None,
        task_name: str = "Gemma inspection agent",
        request_timeout_sec: float | None = None,
        deadline_monotonic: float | None = None,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        model = self.resolve_model_name(model) or DEFAULT_MODEL_NAME  # single model
        full_prompt = (
            f"{prompt}\n\nReturn ONLY one valid JSON object matching this schema. "
            f"No markdown, no extra text.\nSCHEMA:\n{json.dumps(response_schema)}"
        )
        parts: list[Any] = [full_prompt]
        image_parts = [normalize_for_gemma(b, m) for b, m in (image_parts or [])]
        for image_bytes, mime_type in image_parts:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        # Keep enough room for structured findings without letting output budgets
        # grow to 8K tokens for every agent call.
        tokens = min(max(max_output_tokens, 768), 1200)

        def _run_request(operation):
            options = {}
            if max_attempts is not None:
                options["max_attempts"] = max_attempts
            if request_timeout_sec is not None:
                remaining = deadline_monotonic - time.monotonic() if deadline_monotonic is not None else request_timeout_sec
                if remaining <= 0:
                    raise TimeoutError("Inspection exceeded its 120-second time limit.")
                if deadline_monotonic is not None and remaining < 10:
                    raise TimeoutError("Inspection stopped before the 120-second limit because Google requires a 10-second minimum request timeout.")
                options["timeout_sec"] = min(request_timeout_sec, remaining)
            return self._with_retry(operation, **options)

        # NOTE: response_schema is NOT sent: Gemma 4 returns 500 INTERNAL with it.
        def _make_op(mime_json: bool, temp: float):
            cfg: dict[str, Any] = {"temperature": temp, "max_output_tokens": tokens}
            if mime_json:
                cfg["response_mime_type"] = "application/json"

            def _op(client: genai.Client):
                return client.models.generate_content(model=model, contents=parts, config=cfg)

            return _op

        last_raw = ""
        last_api_error: Exception | None = None
        modes = ((True, temperature),) if max_attempts is not None else ((True, temperature), (False, 0.1))
        for mime_json, temp in modes:
            try:
                response = _run_request(_make_op(mime_json, temp))
                last_api_error = None
                try:
                    last_raw = self._extract_text(response)
                except Exception:
                    last_raw = ""
                parsed = self._try_parse_json_response(response)
            except Exception as exc:  # API error: fall through to the next attempt
                last_api_error = exc
                print(f"[Gemma request failed] agent={task_name!r} json_mode={mime_json} error={str(exc)[:240]!r}", flush=True)
                if ApiKeyPool._classify_error(str(exc)) == "rate_limit":
                    raise RuntimeError(f"{task_name} stopped: Gemini API rate limit reached. Retry after the quota resets.") from exc
                # Transport failures are not JSON formatting failures. Let the run router
                # switch models immediately instead of spending another full timeout.
                raise RuntimeError(f"{task_name} upstream request failed: {exc}") from exc
            if parsed is not None:
                return GeneratedJSON(parsed, model)
            print(f"[Gemma response was not JSON] agent={task_name!r} json_mode={mime_json}", flush=True)

        if last_api_error is not None and not last_raw:
            raise RuntimeError(f"{task_name} could not reach Gemma successfully: {last_api_error}") from last_api_error

        # Make one focused repair request using the actual invalid output. This
        # avoids failing the entire five-agent run on a small formatting mistake.
        repair_prompt = (
            "Convert the model output below into exactly one valid JSON object matching the schema. "
            "Preserve only supported facts; do not add findings or measurements. Return JSON only.\n\n"
            f"SCHEMA:\n{json.dumps(response_schema, ensure_ascii=False)}\n\n"
            f"MODEL OUTPUT:\n{last_raw[:7000]}"
        ) if last_raw else (
            f"{full_prompt}\n\nThe previous response was empty or not parseable. "
            "Complete the requested task and return exactly one valid JSON object."
        )
        repair_parts: list[Any] = [repair_prompt]
        if not last_raw:
            for image_bytes, mime_type in image_parts or []:
                repair_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

        repair_errors: list[str] = []
        repair_modes = (True,) if max_attempts is not None else (True, False)
        for mime_json in repair_modes:
            config: dict[str, Any] = {"temperature": 0.0, "max_output_tokens": tokens}
            if mime_json:
                config["response_mime_type"] = "application/json"
            try:
                repaired = _run_request(lambda client: client.models.generate_content(
                    model=model, contents=repair_parts, config=config
                ))
                parsed = self._try_parse_json_response(repaired)
                if parsed is not None:
                    return GeneratedJSON(parsed, model)
            except Exception as exc:
                repair_errors.append(str(exc)[:200])

        if last_api_error is not None:
            raise RuntimeError(f"{task_name} failed: Gemma API error ({last_api_error}); JSON repair also failed.") from last_api_error
        detail = f"; repair errors: {' | '.join(repair_errors)}" if repair_errors else ""
        raise RuntimeError(f"{task_name} returned invalid JSON after one repair attempt{detail}")

    def probe_vision_models(
        self,
        *,
        candidate_models: list[str],
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        for model in candidate_models:
            try:
                text = self._probe_vision_once_via_rest(
                    model=model,
                    encoded_image=encoded_image,
                    mime_type=mime_type,
                )
                sample = text[:120] if text else "(empty text response)"
                rows.append({"model": model, "vision_callable": True, "sample_response": sample})
            except Exception as exc:
                rows.append({"model": model, "vision_callable": False, "error": str(exc)[:200]})

        return rows

    def _probe_vision_once_via_rest(self, *, model: str, encoded_image: str, mime_type: str) -> str:
        attempts = max(1, min(3, len(self.api_keys)))
        last_error: Exception | None = None

        for _ in range(attempts):
            try:
                slot = self.key_pool.acquire()
            except KeyUnavailableError as exc:
                wait_seconds = self.key_pool.next_available_in_seconds()
                if wait_seconds != float("inf"):
                    time.sleep(min(wait_seconds, 1.0))
                    last_error = exc
                    continue
                last_error = exc
                break

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": "Does this image show any manufacturing defect? Reply in one short sentence."},
                            {"inline_data": {"mime_type": mime_type, "data": encoded_image}},
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 40},
            }

            try:
                response = requests.post(
                    url,
                    params={"key": slot.key},
                    json=payload,
                    timeout=7,
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"{response.status_code} {response.text[:180]}")

                body = response.json()
                text = self._extract_text_from_rest_response(body)
                self.key_pool.report_success(slot)
                return text
            except Exception as exc:
                self.key_pool.report_failure(slot, exc)
                last_error = exc

        if last_error:
            raise last_error
        raise RuntimeError("Vision probe failed without specific error")

    @staticmethod
    def _extract_text_from_rest_response(body: dict[str, Any]) -> str:
        candidates = body.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        chunks = [part.get("text", "") for part in parts if part.get("text")]
        return "\n".join(chunks).strip()

    def key_pool_status(self) -> list[dict]:
        return self.key_pool.status()

    @staticmethod
    def _extract_text(response: Any) -> str:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            raise ValueError("Gemini returned an empty response")
        content = getattr(candidates[0], "content", None)
        parts = (getattr(content, "parts", None) if content else None) or []
        plain = [p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)]
        every = [p.text for p in parts if getattr(p, "text", None)]
        text = "\n".join(plain) or "\n".join(every)  # fall back to thinking text if that is all there is
        if not text:
            text = getattr(response, "text", None) or ""
        return text

    # ------------------------------------------------------------------
    # PCB crop-level methods (ported from pcb-analysis gemini_client)
    # ------------------------------------------------------------------

    def classify_crop(
        self,
        crop_raw: bytes,
        crop_highlighted: bytes,
        *,
        model: str = DEFAULT_MODEL_NAME,
        mime_type: str = "image/png",
        temperature: float = 0.1,
    ) -> GeminiDefectResponse:
        """Classify a diff crop using raw + highlighted images.

        Uses the multi-key pool with retry logic.
        """
        def _op(client: genai.Client) -> GeminiDefectResponse:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(data=crop_raw, mime_type=mime_type),
                            types.Part.from_bytes(data=crop_highlighted, mime_type=mime_type),
                            types.Part.from_text(text=CROP_CLASSIFICATION_PROMPT),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=GeminiDefectResponse,
                ),
            )
            return GeminiDefectResponse.model_validate_json(response.text)

        try:
            return self._with_retry(_op)
        except Exception:
            return GeminiDefectResponse(
                defect_type="unknown",
                description="Classification failed due to an API error.",
                severity="medium",
            )

    def annotate_crop(
        self,
        crop_bytes: bytes,
        defect_type: str,
        severity: str,
        description: str,
        *,
        model: str = DEFAULT_MODEL_NAME,
        mime_type: str = "image/png",
        temperature: float = 0.1,
    ) -> bytes | None:
        """Send a diff crop to Gemini and get back the crop with annotations.

        Returns annotated crop as image bytes, or None on failure.
        """
        prompt = ANNOTATE_CROP_PROMPT.format(
            defect_type=defect_type,
            severity=severity,
            description=description,
        )

        def _op(client: genai.Client) -> bytes | None:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(data=crop_bytes, mime_type=mime_type),
                            types.Part.from_text(text=prompt),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    return part.inline_data.data
            return None

        try:
            return self._with_retry(_op)
        except Exception:
            return None

    @staticmethod
    def _try_parse_json_response(response: Any) -> dict[str, Any] | None:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, dict):
            return parsed
        if parsed is not None and hasattr(parsed, "model_dump"):
            dumped = parsed.model_dump()
            if isinstance(dumped, dict):
                return dumped

        text = GeminiService._extract_text(response)
        if not text:
            return None
        try:
            return safe_json_loads(text)
        except Exception:
            return None

    def embed_texts(self, *, model: str, texts: list[str]) -> list[list[float]]:
        """Generate semantic vectors through the same API-key pool used for Gemma."""
        def _op(client):
            return client.models.embed_content(model=model, contents=texts)

        response = self._with_retry(_op)
        embeddings = getattr(response, "embeddings", None) or []
        return [list(getattr(item, "values", []) or []) for item in embeddings]
