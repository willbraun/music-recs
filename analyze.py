from functools import lru_cache
from pathlib import Path

import mlx.core as mx
from mlx_audio.stt.utils import load_model

MODEL_ID = "mlx-community/Qwen2-Audio-7B-Instruct-4bit"
PROMPT = "You are an expert music recommender. Evaluate whether you would recommend the given song to me based on my musical taste. My taste is:"
OUTPUT_FORMAT = "Respond with exactly one word: YES or NO (YES only if I would like this song)."

# Explicit exclusions in the taste stay hard NOs at every level.
STRICT_GUIDANCE = "Say YES only if the song closely fits my taste."
BALANCED_GUIDANCE = "Say YES if the song fits my taste or is a clear neighbor of it."
OPEN_GUIDANCE = (
    "Say YES if the song shares qualities I like (mood, energy, production, vocal style), "
    "even if its genre or artist is not listed. Explicit exclusions and language requirements still mean NO."
)


def _pick_guidance(exploration: int) -> str:
    if exploration < 34:
        return STRICT_GUIDANCE
    if exploration < 67:
        return BALANCED_GUIDANCE
    return OPEN_GUIDANCE


@lru_cache(maxsize=1)
def _load():
    return load_model(MODEL_ID)


@lru_cache(maxsize=1)
def _get_answer_token_ids() -> tuple[int, int]:
    tokenizer = _load()._processor.tokenizer
    yes_id, no_id = (tokenizer.encode(word, add_special_tokens=False)[0] for word in ("YES", "NO"))
    return yes_id, no_id


def analyze(audio_path: Path, taste: str, exploration: int) -> str:
    model = _load()
    prompt = f"{PROMPT} {taste}\n\n{_pick_guidance(exploration)}\n\n{OUTPUT_FORMAT}"
    # The model only listens to the first 30 seconds of audio.
    _, inputs_embeds, _ = model.get_input_embeddings(str(audio_path), prompt)

    # Compute the probability of the next token being YES or NO and determine the verdict.
    next_token_logits = model(None, input_embeddings=inputs_embeds)[0, -1]
    yes_id, no_id = _get_answer_token_ids()
    yes_probability = mx.softmax(next_token_logits[mx.array([yes_id, no_id])].astype(mx.float32))[0].item()
    is_yes = yes_probability >= 0.5
    confidence = yes_probability if is_yes else 1 - yes_probability
    return f"Verdict: {'YES' if is_yes else 'NO'} ({confidence:.0%} confidence)"
