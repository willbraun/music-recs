from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from embed import embed_text
from sklearn.linear_model import LogisticRegression
from taste_profile import TasteProfile

MIN_PER_CLASS = 3
HEAD_HALF_RATINGS = 20
THRESHOLD_STRICT = 0.7
THRESHOLD_OPEN = 0.4
# Measured on 23 analyzed songs: cosine to the genre anchor was -0.13 to 0.16 (mean 0.02, std 0.08).
PRIOR_MID = 0.07
PRIOR_SCALE = 0.04
# Measured on 46 analyzed songs: audio cosine to the mean of the artist's other songs was 0.63 on average,
# against 0.46 for other artists' songs (90th percentile 0.71).
ARTIST_MID = 0.6
ARTIST_SCALE = 0.08


def get_threshold(exploration: int) -> float:
    return THRESHOLD_STRICT - (THRESHOLD_STRICT - THRESHOLD_OPEN) * exploration / 100


def _build_anchor(genres: list[str]) -> np.ndarray | None:
    if not genres:
        return None
    mean = embed_text([f"{genre} music" for genre in genres]).mean(axis=0)
    return mean / np.linalg.norm(mean)


def _build_artist_anchor(embeddings: Sequence[np.ndarray]) -> np.ndarray | None:
    if not len(embeddings):
        return None
    mean = np.stack([embedding / np.linalg.norm(embedding) for embedding in embeddings]).mean(axis=0)
    return mean / np.linalg.norm(mean)


def _sigmoid(value: float) -> float:
    return float(1 / (1 + np.exp(-value)))


@dataclass
class Scorer:
    positive: np.ndarray
    negative: np.ndarray | None = None
    head: LogisticRegression | None = None
    rating_count: int = 0
    artist: np.ndarray | None = None

    def get_prior(self, embedding: np.ndarray) -> float:
        similarity = float(embedding @ self.positive)
        if self.negative is not None:
            similarity -= float(embedding @ self.negative)
        prior = _sigmoid((similarity - PRIOR_MID) / PRIOR_SCALE)
        if self.artist is not None:
            prior = max(prior, _sigmoid((float(embedding @ self.artist) - ARTIST_MID) / ARTIST_SCALE))
        return prior

    def get_head_weight(self) -> float:
        return self.rating_count / (self.rating_count + HEAD_HALF_RATINGS)

    def score(self, embedding: np.ndarray) -> float:
        prior = self.get_prior(embedding)
        if self.head is None:
            return prior
        embedding = embedding / np.linalg.norm(embedding)
        head = float(self.head.predict_proba(embedding.reshape(1, -1))[0, 1])
        weight = self.get_head_weight()
        return (1 - weight) * prior + weight * head


def build_scorer(
    profile: TasteProfile,
    rated: list[tuple[np.ndarray, int]],
    artist_embeddings: Sequence[np.ndarray] = (),
) -> Scorer:
    """Build the scorer from the taste's genres, the rated songs' embeddings (rating 1 or -1), and the embeddings
    of songs by the taste's liked artists."""
    positive = _build_anchor(profile.liked_genres)
    if positive is None:
        raise ValueError("The taste needs at least one liked genre")
    scorer = Scorer(positive, _build_anchor(profile.disliked_genres), artist=_build_artist_anchor(artist_embeddings))

    likes = sum(1 for _, rating in rated if rating == 1)
    dislikes = len(rated) - likes
    if likes >= MIN_PER_CLASS and dislikes >= MIN_PER_CLASS:
        features = np.stack([embedding / np.linalg.norm(embedding) for embedding, _ in rated])
        labels = np.array([1 if rating == 1 else 0 for _, rating in rated])
        scorer.head = LogisticRegression(class_weight="balanced").fit(features, labels)
        scorer.rating_count = len(rated)
    return scorer
