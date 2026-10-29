import re
from dataclasses import dataclass

from pydantic import BaseModel

MAX_ITEMS = 50
MAX_ITEM_CHARS = 100
MAX_NOTES_CHARS = 1000
MAX_TEXT_CHARS = 2000


class TasteProfile(BaseModel):
    liked_genres: list[str] = []
    liked_artists: list[str] = []
    disliked_genres: list[str] = []
    disliked_artists: list[str] = []
    notes: str = ""


@dataclass
class Taste:
    profile: TasteProfile
    updated_at: str

    @property
    def text(self) -> str:
        return render_taste(self.profile)


def _normalize_items(items: list[str], label: str) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        item = item.strip()
        if not item or item.casefold() in seen:
            continue
        if len(item) > MAX_ITEM_CHARS:
            raise ValueError(f"Each {label} entry must be at most {MAX_ITEM_CHARS} characters")
        seen.add(item.casefold())
        result.append(item)
    if len(result) > MAX_ITEMS:
        raise ValueError(f"{label.capitalize()} can have at most {MAX_ITEMS} entries")
    return result


def render_taste(profile: TasteProfile) -> str:
    # The frontend never renders this text, so there is one implementation. Sentences with empty lists are omitted.
    sentences = [
        ("I like these genres: ", profile.liked_genres),
        ("My favorite artists are ", profile.liked_artists),
        ("Never recommend these genres: ", profile.disliked_genres),
        ("Never recommend these artists: ", profile.disliked_artists),
    ]
    parts = [f"{prefix}{', '.join(items)}." for prefix, items in sentences if items]
    if profile.notes:
        parts.append(f"Notes: {profile.notes}")
    return " ".join(parts)


def normalize_taste(profile: TasteProfile) -> TasteProfile:
    """Return the cleaned profile, or raise ValueError with the first rule that failed."""
    # Items are trimmed and deduplicated ignoring case, keeping the first spelling; notes become one paragraph.
    normalized = TasteProfile(
        liked_genres=_normalize_items(profile.liked_genres, "liked genre"),
        liked_artists=_normalize_items(profile.liked_artists, "liked artist"),
        disliked_genres=_normalize_items(profile.disliked_genres, "disliked genre"),
        disliked_artists=_normalize_items(profile.disliked_artists, "disliked artist"),
        notes=re.sub(r"\s*[\r\n]+\s*", " ", profile.notes).strip(),
    )
    if len(normalized.notes) > MAX_NOTES_CHARS:
        raise ValueError(f"Notes must be at most {MAX_NOTES_CHARS} characters")

    for kind, liked, disliked in (
        ("genre", normalized.liked_genres, normalized.disliked_genres),
        ("artist", normalized.liked_artists, normalized.disliked_artists),
    ):
        disliked_keys = {item.casefold() for item in disliked}
        for item in liked:
            if item.casefold() in disliked_keys:
                raise ValueError(f"{item} is in both your liked and disliked {kind}s")

    if not normalized.liked_genres and not normalized.liked_artists:
        raise ValueError("Add at least one liked genre or artist")
    # Keeps the audio model's prompt small.
    if len(render_taste(normalized)) > MAX_TEXT_CHARS:
        raise ValueError(f"Your taste is too long. Keep it under {MAX_TEXT_CHARS} characters in total")
    return normalized
