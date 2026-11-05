from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


class KeyUnavailableError(RuntimeError):
    """Raised when no API key is currently available."""


@dataclass
class ApiKeySlot:
    index: int
    key: str
    fail_count: int = 0
    disabled_until_epoch: float = 0.0
    invalid: bool = False
    last_error: str | None = None
    success_count: int = 0

    @property
    def masked(self) -> str:
        if len(self.key) <= 10:
            return self.key
        return f"{self.key[:6]}...{self.key[-4:]}"


@dataclass
class ApiKeyPool:
    keys: list[str]
    base_backoff_seconds: int = 2
    max_backoff_seconds: int = 120
    _cursor: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("At least one Gemini API key is required")
        self._slots = [ApiKeySlot(index=i, key=k) for i, k in enumerate(self.keys)]

    def acquire(self) -> ApiKeySlot:
        now = time.time()
        with self._lock:
            available_indices = []
            for _ in range(len(self._slots)):
                idx = self._cursor % len(self._slots)
                self._cursor += 1
                slot = self._slots[idx]
                if slot.invalid:
                    continue
                if slot.disabled_until_epoch > now:
                    continue
                available_indices.append(idx)
                break

            if not available_indices:
                raise KeyUnavailableError("No healthy Gemini API key available (all keys cooling down or invalid)")

            return self._slots[available_indices[0]]

    def report_success(self, slot: ApiKeySlot) -> None:
        with self._lock:
            slot.fail_count = 0
            slot.disabled_until_epoch = 0.0
            slot.last_error = None
            slot.success_count += 1

    def report_failure(self, slot: ApiKeySlot, error: Exception | str) -> None:
        message = str(error)
        mode = self._classify_error(message)

        with self._lock:
            slot.fail_count += 1
            slot.last_error = message[:300]

            if mode == "invalid":
                slot.invalid = True
                slot.disabled_until_epoch = float("inf")
                return

            if mode == "rate_limit":
                backoff = min(
                    self.max_backoff_seconds,
                    self.base_backoff_seconds * (2 ** max(0, slot.fail_count - 1)),
                )
                slot.disabled_until_epoch = time.time() + backoff
                return

            # transient/unknown errors: keep cooldown very short.
            slot.disabled_until_epoch = time.time() + 0.5

    def next_available_in_seconds(self) -> float:
        now = time.time()
        with self._lock:
            waits = []
            for slot in self._slots:
                if slot.invalid:
                    continue
                waits.append(max(0.0, slot.disabled_until_epoch - now))
            if not waits:
                return float("inf")
            return min(waits)

    def status(self) -> list[dict]:
        now = time.time()
        with self._lock:
            rows = []
            for slot in self._slots:
                cooldown = 0.0 if slot.invalid else max(0.0, slot.disabled_until_epoch - now)
                rows.append(
                    {
                        "index": slot.index,
                        "key_masked": slot.masked,
                        "invalid": slot.invalid,
                        "cooldown_seconds": round(cooldown, 2),
                        "fail_count": slot.fail_count,
                        "success_count": slot.success_count,
                        "last_error": slot.last_error,
                    }
                )
            return rows

    @staticmethod
    def _classify_error(message: str) -> str:
        upper = message.upper()
        if "API_KEY_INVALID" in upper or "API KEY NOT VALID" in upper:
            return "invalid"
        if "RESOURCE_EXHAUSTED" in upper or "RATE" in upper and "LIMIT" in upper:
            return "rate_limit"
        if "429" in upper or "QUOTA" in upper:
            return "rate_limit"
        return "transient"
