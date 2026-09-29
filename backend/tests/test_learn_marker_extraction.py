from app.services.note_service import extract_note_markers


def test_marker_uses_exact_selection_and_keeps_full_context() -> None:
    body = {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "attrs": {
                "pmId": "abc12345",
                "learn": "lernen",
                "learnText": "nur dieser Teil",
                "learnFrom": 4,
                "learnTo": 19,
            },
            "content": [{"type": "text", "text": "Der ganze Absatz enthält nur dieser Teil als Lernstoff."}],
        }],
    }

    marker = extract_note_markers(body)[0]

    assert marker["snippet"] == "nur dieser Teil"
    assert marker["context"] == "Der ganze Absatz enthält nur dieser Teil als Lernstoff."


def test_marker_without_selection_uses_whole_block() -> None:
    body = {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "attrs": {"pmId": "abc12345", "learn": "lernen"},
            "content": [{"type": "text", "text": "  Ganzer   Absatz  "}],
        }],
    }

    marker = extract_note_markers(body)[0]

    assert marker["snippet"] == "Ganzer Absatz"
    assert marker["context"] == "Ganzer Absatz"
