from pydantic import BaseModel

MAX_ITEMS = 50
MAX_ITEM_LENGTH = 100
MAX_NOTES_LENGTH = 2000


class TasteProfile(BaseModel):
    liked_genres: list[str] = []
    liked_artists: list[str] = []
    disliked_genres: list[str] = []
    disliked_artists: list[str] = []
    notes: str = ""


def _clean_items(label: str, items: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned = []
    for item in items:
        item = item.strip()
        # The first spelling is kept, in entry order.
        if item and item.casefold() not in seen:
            seen.add(item.casefold())
            cleaned.append(item)
    if len(cleaned) > MAX_ITEMS:
        raise ValueError(f"{label} can have at most {MAX_ITEMS} items")
    if any(len(item) > MAX_ITEM_LENGTH for item in cleaned):
        raise ValueError(f"Each item in {label} can have at most {MAX_ITEM_LENGTH} characters")
    return cleaned


def _find_conflict(liked: list[str], disliked: list[str]) -> str | None:
    disliked_keys = {item.casefold() for item in disliked}
    return next((item for item in liked if item.casefold() in disliked_keys), None)


def normalize_profile(profile: TasteProfile) -> TasteProfile:
    """Trim and deduplicate the fields; raise ValueError with a readable message for the first rule that fails."""
    liked_genres = _clean_items("Liked genres", profile.liked_genres)
    liked_artists = _clean_items("Liked artists", profile.liked_artists)
    disliked_genres = _clean_items("Disliked genres", profile.disliked_genres)
    disliked_artists = _clean_items("Disliked artists", profile.disliked_artists)
    notes = profile.notes.strip()

    if not liked_genres:
        raise ValueError("Choose at least one liked genre")
    if genre := _find_conflict(liked_genres, disliked_genres):
        raise ValueError(f"{genre} cannot be both liked and disliked")
    if artist := _find_conflict(liked_artists, disliked_artists):
        raise ValueError(f"{artist} cannot be both liked and disliked")
    if len(notes) > MAX_NOTES_LENGTH:
        raise ValueError(f"Notes can have at most {MAX_NOTES_LENGTH} characters")

    return TasteProfile(
        liked_genres=liked_genres,
        liked_artists=liked_artists,
        disliked_genres=disliked_genres,
        disliked_artists=disliked_artists,
        notes=notes,
    )


def render_taste(profile: TasteProfile) -> str:
    """Render the text used for query generation. Disliked artists are left out, since they are filtered in code."""
    sentences = [
        ("I like these genres: ", profile.liked_genres),
        ("My favorite artists are ", profile.liked_artists),
        ("Avoid these genres: ", profile.disliked_genres),
    ]
    parts = [f"{prefix}{', '.join(items)}." for prefix, items in sentences if items]
    if profile.notes:
        parts.append(f"Notes: {profile.notes}")
    return " ".join(parts)
