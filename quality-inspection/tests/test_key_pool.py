import pytest

from app.key_pool import ApiKeyPool, KeyUnavailableError


def test_round_robin_order() -> None:
    pool = ApiKeyPool(keys=["k1", "k2", "k3"])

    s1 = pool.acquire()
    pool.report_success(s1)
    s2 = pool.acquire()
    pool.report_success(s2)
    s3 = pool.acquire()
    pool.report_success(s3)

    assert [s1.key, s2.key, s3.key] == ["k1", "k2", "k3"]


def test_invalid_key_is_removed_from_rotation() -> None:
    pool = ApiKeyPool(keys=["k1", "k2"])

    first = pool.acquire()
    pool.report_failure(first, "API_KEY_INVALID")

    second = pool.acquire()
    assert second.key == "k2"


def test_single_rate_limited_key_becomes_unavailable() -> None:
    pool = ApiKeyPool(keys=["k1"])

    slot = pool.acquire()
    pool.report_failure(slot, "429 RESOURCE_EXHAUSTED")

    with pytest.raises(KeyUnavailableError):
        pool.acquire()
