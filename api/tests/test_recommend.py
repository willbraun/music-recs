import pytest
from recommend import get_verdict


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Verdict: YES (90% confidence)", True),
        ("Verdict: NO (60% confidence)", False),
        ("  verdict:   yes", True),
        ("VERDICT: NO", False),
    ],
)
def test_get_verdict_parses_yes_and_no(description: str, expected: bool) -> None:
    assert get_verdict(description) is expected


@pytest.mark.parametrize("description", ["", "YES", "Verdict: MAYBE", "Verdict: YESTERDAY", "Result. Verdict: YES"])
def test_get_verdict_returns_none_without_a_verdict(description: str) -> None:
    assert get_verdict(description) is None
