from app.core.text import sanitize_text_for_db


def test_sanitize_text_for_db_removes_nul_bytes() -> None:
    assert sanitize_text_for_db("A\x00B\x00C") == "ABC"


def test_sanitize_text_for_db_handles_none_and_empty() -> None:
    assert sanitize_text_for_db(None) == ""
    assert sanitize_text_for_db("") == ""

