from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any

from .gemini_client import GeminiService


class RunModelRouter:
    """Shares ordered model fallbacks across one report run."""

    def __init__(self, primary: str, progress=None, deadline_seconds: float = 120) -> None:
        self.primary = primary
        self.fallback_models = [
            model for model in ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest")
            if model != primary
        ]
        self.progress = progress
        self.deadline = monotonic() + deadline_seconds
        self._fallback_index = -1
        self._lock = Lock()

    @property
    def fallback_active(self) -> bool:
        with self._lock:
            return self._fallback_index >= 0

    def current_model(self) -> str:
        with self._lock:
            return self.fallback_models[self._fallback_index] if self._fallback_index >= 0 else self.primary

    def remaining_seconds(self) -> float:
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Inspection exceeded its 120-second time limit.")
        return remaining

    def advance_after_failure(self, failed_model: str) -> str | None:
        switched = False
        with self._lock:
            active_model = self.fallback_models[self._fallback_index] if self._fallback_index >= 0 else self.primary
            if active_model != failed_model:
                return active_model  # A parallel agent already advanced the shared route.
            if self._fallback_index + 1 < len(self.fallback_models):
                self._fallback_index += 1
                switched = True
            else:
                return None
            next_model = self.fallback_models[self._fallback_index]
        if switched and self.progress:
            self.progress("fallback")
        return next_model


class AgentResult(dict):
    def __init__(self, values: dict, model_used: str):
        super().__init__(values)
        self.model_used = model_used
from .prompts import (
    DESIGN_SCHEMA,
    PHYSICAL_SCHEMA,
    SPEC_PRECHECK_SCHEMA,
    SPEC_FINAL_SCHEMA,
    SYMPTOM_SCHEMA,
    base_context,
    design_prompt,
    physical_prompt,
    spec_precheck_prompt,
    spec_final_prompt,
    symptom_prompt,
)


@dataclass
class AgentRunner:
    gemini: GeminiService
    model: str
    temperature: float
    max_output_tokens: int
    background_context: str
    todo_context: str
    example_context: str
    router: RunModelRouter | None = None

    def _generate(self, *, task_name: str, image_parts=None, **kwargs):
        router = self.router
        model = router.current_model() if router else self.model
        while True:
            if router and router.remaining_seconds() < 10:
                raise TimeoutError("Inspection stopped before the 120-second limit to avoid a request shorter than Google's 10-second minimum.")
            try:
                result = self.gemini.generate_json(
                    task_name=task_name,
                    model=model,
                    image_parts=image_parts,
                    request_timeout_sec=10.0,
                    deadline_monotonic=router.deadline if router else None,
                    max_attempts=1,
                    **kwargs,
                )
                break
            except Exception as exc:
                message = str(exc).upper()
                retryable = any(marker in message for marker in (
                    "504", "DEADLINE_EXCEEDED", "TIMED OUT", "TIMEOUT", "503",
                    "SERVICE UNAVAILABLE", "MODEL NOT FOUND", "NOT_FOUND", "UNAVAILABLE",
                    "404", "500 INTERNAL", "429", "RESOURCE_EXHAUSTED", "RATE LIMIT", "QUOTA",
                ))
                # Vision requests already try the ordered VISION_MODELS list themselves.
                if not router or not retryable or image_parts:
                    raise
                next_model = router.advance_after_failure(model)
                if not next_model:
                    raise
                model = next_model
        actual_model = getattr(result, "model_used", model)
        return AgentResult(result, actual_model)

    def _context(self) -> str:
        return base_context(
            background=self.background_context,
            todo=self.todo_context,
            example=self.example_context,
        )

    def run_symptom_agent(
        self,
        error_log: str,
        *,
        spec_focus_plan: str | None = None,
        spec_image_parts: list[tuple[bytes, str]] | None = None,
    ) -> dict:
        prompt = symptom_prompt(
            context=self._context(),
            error_log=error_log,
            spec_focus_plan=spec_focus_plan,
        )
        return self._generate(
            task_name="Error Analyzer",
            prompt=prompt,
            response_schema=SYMPTOM_SCHEMA,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            image_parts=spec_image_parts,
        )

    def run_spec_precheck_agent(self, spec_excerpt: str, symptom_result: dict) -> dict:
        prompt = spec_precheck_prompt(
            context=self._context(),
            spec_excerpt=spec_excerpt,
            symptom_result=symptom_result,
        )
        return self._generate(
            task_name="Spec Checker",
            prompt=prompt,
            response_schema=SPEC_PRECHECK_SCHEMA,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

    def run_design_agent(
        self,
        symptom_result: dict,
        heuristic_bbox: dict | None,
        design_reference_text: str | None,
        design_image: tuple[bytes, str],
    ) -> dict:
        prompt = design_prompt(
            context=self._context(),
            symptom_result=symptom_result,
            heuristic_bbox=heuristic_bbox,
            design_reference_text=design_reference_text,
        )
        return self._generate(
            task_name="CAD Mapper",
            prompt=prompt,
            response_schema=DESIGN_SCHEMA,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            image_parts=[design_image],
        )

    def run_physical_agent(
        self,
        symptom_result: dict,
        spec_precheck_result: dict,
        design_result: dict,
        heuristic_bbox: dict | None,
        tested_image: tuple[bytes, str],
    ) -> dict:
        prompt = physical_prompt(
            context=self._context(),
            symptom_result=symptom_result,
            spec_precheck_result=spec_precheck_result,
            design_result=design_result,
            heuristic_bbox=heuristic_bbox,
        )
        return self._generate(
            task_name="Defect Inspector",
            prompt=prompt,
            response_schema=PHYSICAL_SCHEMA,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            image_parts=[tested_image],
        )

    def run_spec_final_agent(
        self,
        spec_excerpt: str,
        symptom_result: dict,
        spec_precheck_result: dict,
        design_result: dict,
        physical_result: dict,
    ) -> dict:
        prompt = spec_final_prompt(
            context=self._context(),
            spec_excerpt=spec_excerpt,
            symptom_result=symptom_result,
            spec_precheck_result=spec_precheck_result,
            design_result=design_result,
            physical_result=physical_result,
        )
        return self._generate(
            task_name="Spec Resolution",
            prompt=prompt,
            response_schema=SPEC_FINAL_SCHEMA,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
