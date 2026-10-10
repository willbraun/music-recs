import pytest
import taste_profile
from taste_profile import TasteProfile, normalize_profile, render_taste


def _profile(**fields) -> TasteProfile:
    return TasteProfile(**{"liked_genres": ["Rock"], **fields})


def test_normalize_trims_drops_empties_and_dedupes_ignoring_case() -> None:
    result = normalize_profile(_profile(liked_genres=[" Rock ", "rock", "", "Jazz"], liked_artists=["Flume", "FLUME"], notes="  hi "))

    assert result.liked_genres == ["Rock", "Jazz"]
    assert result.liked_artists == ["Flume"]
    assert result.notes == "hi"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"liked_genres": []}, "at least one liked genre"),
        ({"liked_genres": [" "]}, "at least one liked genre"),
        ({"liked_genres": [f"g{i}" for i in range(taste_profile.MAX_ITEMS + 1)]}, "at most 50 items"),
        ({"liked_artists": ["x" * (taste_profile.MAX_ITEM_LENGTH + 1)]}, "at most 100 characters"),
        ({"disliked_genres": ["rock"]}, "Rock cannot be both"),
        ({"liked_artists": ["Flume"], "disliked_artists": ["flume"]}, "Flume cannot be both"),
        ({"notes": "x" * (taste_profile.MAX_NOTES_LENGTH + 1)}, "Notes can have at most 2000"),
    ],
)
def test_normalize_rejects_invalid_profiles(fields: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_profile(_profile(**fields))


def test_normalize_accepts_limits() -> None:
    result = normalize_profile(_profile(notes="x" * taste_profile.MAX_NOTES_LENGTH, liked_artists=["x" * 100]))

    assert len(result.notes) == 2000


def test_render_taste_matches_the_spec_example() -> None:
    profile = TasteProfile(
        liked_genres=["Electronic", "Indie rock"],
        liked_artists=["Tame Impala", "Flume"],
        disliked_genres=["Country"],
        disliked_artists=["Nickelback"],
        notes="I like long instrumental builds.",
    )

    assert render_taste(profile) == (
        "I like these genres: Electronic, Indie rock. My favorite artists are Tame Impala, Flume. "
        "Avoid these genres: Country. Notes: I like long instrumental builds."
    )


def test_render_taste_omits_empty_sentences() -> None:
    assert render_taste(_profile()) == "I like these genres: Rock."
    assert render_taste(_profile(notes="Only notes")) == "I like these genres: Rock. Notes: Only notes"
    assert render_taste(TasteProfile(notes="n")) == "Notes: n"
