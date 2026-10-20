import gc
import json
import math
import random
import re
from dataclasses import dataclass
from functools import lru_cache

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
MAX_NEW_TOKENS = 300
TEMPERATURE = 0.9

TIER_INSTRUCTIONS = {
    "familiar": "a listed favorite artist, or something very close to it",
    "adjacent": "an artist from a related scene that is not named in my taste",
    "adventurous": (
        "an artist not named in my taste, chosen because it shares qualities I like "
        "(mood, energy, production, vocal style)"
    ),
}


@dataclass
class GeneratedQuery:
    query: str
    tier: str


def allocate_tiers(n: int, exploration: int) -> list[str]:
    """Split `n` queries across tiers by weights (1-x)^2, 2x(1-x), x^2 for x = exploration / 100, in shuffled order."""
    x = exploration / 100
    weights = {"familiar": (1 - x) ** 2, "adjacent": 2 * x * (1 - x), "adventurous": x**2}
    counts = {tier: math.floor(n * w) for tier, w in weights.items()}
    # Largest-remainder rounding hands out the queries lost to flooring.
    by_remainder = sorted(weights, key=lambda tier: n * weights[tier] - counts[tier], reverse=True)
    for tier in by_remainder[: n - sum(counts.values())]:
        counts[tier] += 1
    tiers = [tier for tier, count in counts.items() for _ in range(count)]
    random.shuffle(tiers)
    return tiers


@lru_cache(maxsize=1)
def _load():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype="auto", device_map="auto")
    return tokenizer, model


def unload_model() -> None:
    """Release the query model so its memory is free for the audio model."""
    _load.cache_clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def _build_prompt(taste: str, tiers: list[str], avoid_artists: list[str]) -> str:
    lines = "\n".join(f"{i}. {TIER_INSTRUCTIONS[tier]}" for i, tier in enumerate(tiers, 1))
    avoid = f"I have heard these artists too often, so avoid them: {', '.join(avoid_artists)}.\n" if avoid_artists else ""
    return (
        f"My musical taste is: {taste}\n\n"
        f"Write {len(tiers)} search queries for finding songs on YouTube Music, one per line below. "
        "Each query is an artist name with no explanation. "
        "Recommend artists, not specific songs or genres.\n"
        "Never go against the exclusions in my taste.\n"
        f"{avoid}"
        f"{lines}\n\n"
        f"Respond with only a JSON array of {len(tiers)} strings, in the same order."
    )


def _parse(text: str) -> list[str]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match is None:
        return []
    try:
        items = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def _get_fallback_queries(taste: str, liked_artists: list[str]) -> list[str]:
    return list(liked_artists) or [taste[:100]]


def _generate_text(prompt: str) -> str:
    tokenizer, model = _load()
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_dict=True, return_tensors="pt"
    ).to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=True, temperature=TEMPERATURE)
    return tokenizer.decode(outputs[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def generate_queries(
    taste: str, liked_artists: list[str], exploration: int, n: int, avoid_artists: list[str] | None = None
) -> list[GeneratedQuery]:
    """Generate `n` search queries whose distance from `taste` follows `exploration` (0-100).

    `liked_artists` are the fallback queries when the model returns too few. Queries are distinct,
    so fewer than `n` come back when the model and the fallbacks run out of distinct ones.
    The model is asked to avoid `avoid_artists`, and queries naming them are dropped.
    """
    avoid = avoid_artists or []
    avoid_keys = {artist.casefold() for artist in avoid}
    tiers = allocate_tiers(n, exploration)
    text = _generate_text(_build_prompt(taste, tiers, avoid))
    unload_model()

    generated: list[GeneratedQuery] = []
    used: set[str] = set()
    for query, tier in zip(_parse(text), tiers):
        if query.casefold() not in used and query.casefold() not in avoid_keys:
            used.add(query.casefold())
            generated.append(GeneratedQuery(query, tier))
    # Pad with taste-derived queries when the model returned too few.
    fallback = _get_fallback_queries(taste, liked_artists)
    random.shuffle(fallback)
    # Avoided artists are the last resort.
    fallback.sort(key=lambda query: query.casefold() in avoid_keys)
    for query in fallback:
        if len(generated) >= n:
            break
        if query.casefold() not in used:
            used.add(query.casefold())
            generated.append(GeneratedQuery(query, "familiar"))
    return generated
