import pytest
from taste_profile import (MAX_ITEMS, MAX_NOTES_CHARS, MAX_TEXT_CHARS, Taste,
                           TasteProfile, normalize_taste, render_taste)


def test_render_taste_full_profile() -> None:
    profile = TasteProfile(
        liked_genres=["Electronic", "Indie rock"],
        liked_artists=["Tame Impala", "Flume"],
        disliked_genres=["Country"],
        notes="If songs have lyrics, they should be in English.",
    )

    assert render_taste(profile) == (
        "I like these genres: Electronic, Indie rock. My favorite artists are Tame Impala, Flume. "
        "Never recommend these genres: Country. Notes: If songs have lyrics, they should be in English."
    )


def test_render_taste_omits_empty_sentences() -> None:
    assert render_taste(TasteProfile(liked_artists=["Flume"], disliked_artists=["X"])) == (
        "My favorite artists are Flume. Never recommend these artists: X."
    )


def test_taste_text_is_rendered_from_the_profile() -> None:
    assert Taste(TasteProfile(liked_genres=["Rock"]), "2026-10-10 12:00:00").text == "I like these genres: Rock."


def test_normalize_trims_drops_empty_and_dedupes_ignoring_case() -> None:
    profile = TasteProfile(liked_genres=[" Rock ", "", "rock", "Jazz"], liked_artists=["Flume"])

    assert normalize_taste(profile).liked_genres == ["Rock", "Jazz"]


def test_normalize_turns_newlines_in_notes_into_single_spaces() -> None:
    profile = TasteProfile(liked_genres=["Rock"], notes=" one\n\n two\r\nthree ")

    assert normalize_taste(profile).notes == "one two three"


@pytest.mark.parametrize(
    "fields",
    [
        {"liked_genres": [f"g{i}" for i in range(MAX_ITEMS + 1)]},
        {"liked_artists": ["x" * 101]},
        {"notes": "n" * (MAX_NOTES_CHARS + 1)},
        {"disliked_genres": ["rock"]},
        {"disliked_artists": ["FLUME"]},
        {"liked_artists": [f"{i}" + "x" * 90 for i in range(MAX_TEXT_CHARS // 90 + 1)]},
    ],
)
def test_normalize_rejects_invalid_profiles(fields: dict) -> None:
    base = {"liked_genres": ["Rock"], "liked_artists": ["Flume"]}

    with pytest.raises(ValueError):
        normalize_taste(TasteProfile(**{**base, **fields}))


def test_normalize_requires_a_liked_genre_or_artist() -> None:
    with pytest.raises(ValueError, match="at least one liked"):
        normalize_taste(TasteProfile(disliked_genres=["Country"]))
    assert normalize_taste(TasteProfile(liked_artists=["Flume"])).liked_artists == ["Flume"]
