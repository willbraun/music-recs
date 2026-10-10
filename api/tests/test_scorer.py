import numpy as np
import pytest
import scorer
from scorer import Scorer, build_scorer, get_threshold
from taste_profile import TasteProfile

DIM = 8


def _unit(index: int, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    vector = np.eye(DIM, dtype=np.float32)[index]
    vector = vector + noise * np.random.default_rng(seed).normal(size=DIM).astype(np.float32)
    return vector / np.linalg.norm(vector)


@pytest.fixture(autouse=True)
def stub_text_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each genre maps to its own axis; unknown genres map to the last axis."""
    axes = {"rock": 0, "jazz": 1}

    def fake_embed_text(phrases: list[str]) -> np.ndarray:
        return np.stack([_unit(axes.get(p.removesuffix(" music").lower(), DIM - 1)) for p in phrases])

    monkeypatch.setattr(scorer, "embed_text", fake_embed_text)


def _rated(likes: int, dislikes: int) -> list[tuple[np.ndarray, int]]:
    liked = [(_unit(2, 0.1, seed), 1) for seed in range(likes)]
    disliked = [(_unit(3, 0.1, 100 + seed), -1) for seed in range(dislikes)]
    return liked + disliked


def test_prior_ranks_a_song_near_the_positive_anchor_above_one_near_the_negative() -> None:
    result = build_scorer(TasteProfile(liked_genres=["Rock"], disliked_genres=["Jazz"]), [])

    assert result.negative is not None
    assert result.score(_unit(0)) > result.score(_unit(4)) > result.score(_unit(1))


def test_prior_has_no_negative_anchor_without_disliked_genres() -> None:
    result = build_scorer(TasteProfile(liked_genres=["Rock"]), [])

    assert result.negative is None
    assert result.head is None
    assert 0 <= result.score(_unit(0)) <= 1


def test_prior_averages_liked_genres_into_a_normalized_anchor() -> None:
    result = build_scorer(TasteProfile(liked_genres=["Rock", "Jazz"]), [])

    assert np.isclose(np.linalg.norm(result.positive), 1.0)
    assert np.allclose(result.positive, [np.sqrt(0.5), np.sqrt(0.5), 0, 0, 0, 0, 0, 0])


@pytest.mark.parametrize(("likes", "dislikes"), [(0, 0), (2, 5), (5, 2), (3, 0)])
def test_head_is_not_used_below_the_minimum_per_class(likes: int, dislikes: int) -> None:
    result = build_scorer(TasteProfile(liked_genres=["Rock"]), _rated(likes, dislikes))

    assert result.head is None
    assert result.rating_count == 0


def test_head_separates_liked_and_disliked_embeddings() -> None:
    result = build_scorer(TasteProfile(liked_genres=["Rock"]), _rated(5, 5))

    assert result.head is not None
    like_probability = result.head.predict_proba(_unit(2, 0.1, 50).reshape(1, -1))[0, 1]
    dislike_probability = result.head.predict_proba(_unit(3, 0.1, 51).reshape(1, -1))[0, 1]
    assert like_probability > 0.5 > dislike_probability


def test_head_weight_follows_rating_count() -> None:
    result = build_scorer(TasteProfile(liked_genres=["Rock"]), _rated(10, 10))

    assert result.get_head_weight() == 20 / (20 + scorer.HEAD_HALF_RATINGS) == 0.5


def test_score_blends_the_prior_and_the_head() -> None:
    result = build_scorer(TasteProfile(liked_genres=["Rock"]), _rated(10, 10))
    song = _unit(2, 0.1, 50)
    prior = result.get_prior(song)
    head = result.head.predict_proba(song.reshape(1, -1))[0, 1]

    assert result.score(song) == pytest.approx(0.5 * prior + 0.5 * head)


def test_score_without_a_head_is_the_prior() -> None:
    result = Scorer(positive=_unit(0))

    assert result.score(_unit(0)) == result.get_prior(_unit(0))


def test_build_scorer_requires_a_liked_genre() -> None:
    with pytest.raises(ValueError):
        build_scorer(TasteProfile(), [])


def test_artist_songs_raise_the_prior_of_similar_songs() -> None:
    profile = TasteProfile(liked_genres=["Rock"])
    artist_songs = [_unit(5, 0.05, seed) for seed in range(3)]
    without = build_scorer(profile, [])
    with_artist = build_scorer(profile, [], artist_songs)
    similar, unrelated = _unit(5, 0.05, 50), _unit(6)

    assert with_artist.artist is not None
    assert np.isclose(np.linalg.norm(with_artist.artist), 1.0)
    assert with_artist.score(similar) > 0.9 > without.score(similar)
    assert with_artist.score(unrelated) == without.score(unrelated)


def test_prior_has_no_artist_anchor_without_artist_songs() -> None:
    assert build_scorer(TasteProfile(liked_genres=["Rock"]), []).artist is None


def test_threshold_falls_as_exploration_rises() -> None:
    assert get_threshold(0) == scorer.THRESHOLD_STRICT
    assert get_threshold(100) == scorer.THRESHOLD_OPEN
    assert get_threshold(50) == pytest.approx((scorer.THRESHOLD_STRICT + scorer.THRESHOLD_OPEN) / 2)
    assert get_threshold(25) > get_threshold(75)
