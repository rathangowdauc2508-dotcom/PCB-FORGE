from app.config import parse_api_keys


def test_parse_api_keys_bracket_format() -> None:
    raw = "[key1, key2, key3]"
    assert parse_api_keys(raw) == ["key1", "key2", "key3"]


def test_parse_api_keys_csv_and_dedup() -> None:
    raw = " key1, key2, key1 , key3 "
    assert parse_api_keys(raw) == ["key1", "key2", "key3"]


def test_parse_api_keys_empty() -> None:
    assert parse_api_keys(None) == []
    assert parse_api_keys("") == []
