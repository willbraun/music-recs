import pytest
import queries
from queries import GeneratedQuery, allocate_tiers, generate_queries


@pytest.mark.parametrize("exploration", [0, 25, 50, 75, 100])
@pytest.mark.parametrize("n", [0, 1, 5, 6])
def test_allocate_tiers_returns_n_known_tiers(n: int, exploration: int) -> None:
    tiers = allocate_tiers(n, exploration)

    assert len(tiers) == n
    assert set(tiers) <= set(queries.TIER_INSTRUCTIONS)


def test_allocate_tiers_extremes_use_a_single_tier() -> None:
    assert allocate_tiers(6, 0) == ["familiar"] * 6
    assert allocate_tiers(6, 100) == ["adventurous"] * 6


def test_allocate_tiers_splits_evenly_at_midpoint() -> None:
    tiers = allocate_tiers(8, 50)

    assert {tier: tiers.count(tier) for tier in queries.TIER_INSTRUCTIONS} == {"familiar": 2, "adjacent": 4, "adventurous": 2}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('["Tame Impala", "Flume"]', ["Tame Impala", "Flume"]),
        ('Sure! ```json\n["  BORNS ", ""]\n```', ["BORNS"]),
        ('["a", 1, null, "b"]', ["a", "b"]),
        ("no array here", []),
        ("[not json]", []),
    ],
)
def test_parse_extracts_non_empty_strings(text: str, expected: list[str]) -> None:
    assert queries._parse(text) == expected


def test_build_prompt_lists_each_tier_in_order() -> None:
    prompt = queries._build_prompt("indie rock", ["familiar", "adventurous"])

    assert "My musical taste is: indie rock" in prompt
    assert f"1. {queries.TIER_INSTRUCTIONS['familiar']}" in prompt
    assert f"2. {queries.TIER_INSTRUCTIONS['adventurous']}" in prompt
    assert "JSON array of 2 strings" in prompt


def test_get_fallback_queries_uses_favorite_artists() -> None:
    taste = "Rock, blues. My favorite artists are Tame Impala, Flume, Mac Miller. English only."

    assert queries._get_fallback_queries(taste) == ["Tame Impala", "Flume", "Mac Miller"]


def test_get_fallback_queries_truncates_taste_without_artists() -> None:
    assert queries._get_fallback_queries("x" * 150) == ["x" * 100]


@pytest.fixture
def stub_model(monkeypatch: pytest.MonkeyPatch):
    unloaded: list[bool] = []
    monkeypatch.setattr(queries, "unload_model", lambda: unloaded.append(True))
    return unloaded


def test_generate_queries_pairs_parsed_queries_with_tiers(monkeypatch: pytest.MonkeyPatch, stub_model: list[bool]) -> None:
    monkeypatch.setattr(queries, "_generate_text", lambda prompt: '["A", "B"]')

    result = generate_queries("taste", 0, 2)

    assert result == [GeneratedQuery("A", "familiar"), GeneratedQuery("B", "familiar")]
    assert stub_model == [True]


def test_generate_queries_pads_with_fallback_when_model_returns_too_few(
    monkeypatch: pytest.MonkeyPatch, stub_model: list[bool]
) -> None:
    monkeypatch.setattr(queries, "_generate_text", lambda prompt: "garbage")
    taste = "My favorite artists are Flume. Done."

    result = generate_queries(taste, 100, 3)

    assert result == [GeneratedQuery("Flume", "familiar")] * 3


def test_generate_queries_ignores_extra_queries(monkeypatch: pytest.MonkeyPatch, stub_model: list[bool]) -> None:
    monkeypatch.setattr(queries, "_generate_text", lambda prompt: '["A", "B", "C"]')

    assert [g.query for g in generate_queries("taste", 0, 2)] == ["A", "B"]
