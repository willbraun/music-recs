from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import mlx.core as mx
from mlx_audio.stt import load
from model_download import ANALYSIS_MODEL_ID

PROMPT = "You are an expert music recommender. Evaluate whether you would recommend the given song to me based on my musical taste. My taste is:"
OUTPUT_FORMAT = "Respond with exactly one word: YES or NO (YES only if I would like this song)."

# Explicit exclusions in the taste stay hard NOs at every level.
STRICT_GUIDANCE = "Say YES only if the song closely fits my taste."
BALANCED_GUIDANCE = "Say YES if the song fits my taste or is a clear neighbor of it."
OPEN_GUIDANCE = (
    "Say YES if the song shares qualities I like (mood, energy, production, vocal style), "
    "even if its genre or artist is not listed. Explicit exclusions and language requirements still mean NO."
)


class Verdict(NamedTuple):
    recommended: bool
    confidence: float  # Probability of the chosen answer, 0.5 to 1.


def _pick_guidance(exploration: int) -> str:
    if exploration < 34:
        return STRICT_GUIDANCE
    if exploration < 67:
        return BALANCED_GUIDANCE
    return OPEN_GUIDANCE


@lru_cache(maxsize=1)
def _load():
    return load(ANALYSIS_MODEL_ID)


@lru_cache(maxsize=1)
def _get_answer_token_ids() -> tuple[int, int]:
    tokenizer = _load()._ensure_processor().tokenizer
    yes_id, no_id = (tokenizer.encode(word, add_special_tokens=False)[0] for word in ("YES", "NO"))
    return yes_id, no_id


def analyze(audio_path: Path, taste: str, exploration: int) -> Verdict:
    model = _load()
    question = f"{PROMPT} {taste}\n\n{_pick_guidance(exploration)}\n\n{OUTPUT_FORMAT}"
    processed = model._ensure_processor()(text=question, audio=str(audio_path))
    # mlx-audio only exposes sampled text, so the prompt is run through the model directly to read the logits.
    prompt_ids, embeddings, deepstack, _ = model._build_prompt_embeddings(processed)

    # Compute the probability of the next token being YES or NO and determine the verdict.
    next_token_logits = model(prompt_ids[None], input_embeddings=embeddings, deepstack_embeddings=deepstack)[0, -1]
    yes_id, no_id = _get_answer_token_ids()
    yes_probability = mx.softmax(next_token_logits[mx.array([yes_id, no_id])].astype(mx.float32))[0].item()
    is_yes = yes_probability >= 0.5
    confidence = yes_probability if is_yes else 1 - yes_probability
    return Verdict(is_yes, confidence)
