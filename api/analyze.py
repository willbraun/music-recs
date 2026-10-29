from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import torch
from transformers import (AutoConfig, AutoProcessor,
                          Qwen2_5OmniForConditionalGeneration)

MODEL_ID = "Qwen/Qwen2.5-Omni-3B"
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
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    # Only text is read, so the speech generator is never built, which saves about 2 GB.
    config = AutoConfig.from_pretrained(MODEL_ID)
    config.enable_audio_output = False
    model = Qwen2_5OmniForConditionalGeneration.from_pretrained(
        MODEL_ID, config=config, dtype=torch.bfloat16, device_map=device
    )
    return processor, model


@lru_cache(maxsize=1)
def _get_answer_token_ids() -> tuple[int, int]:
    tokenizer = _load()[0].tokenizer
    yes_id, no_id = (tokenizer.encode(word, add_special_tokens=False)[0] for word in ("YES", "NO"))
    return yes_id, no_id


def analyze(audio_path: Path, taste: str, exploration: int) -> Verdict:
    processor, model = _load()
    conversation = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{PROMPT} {taste}\n\n{_pick_guidance(exploration)}\n\n{OUTPUT_FORMAT}"},
                {"type": "audio", "path": str(audio_path)},
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        conversation,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)
    inputs["input_features"] = inputs["input_features"].to(model.dtype)

    # Compute the probability of the next token being YES or NO and determine the verdict.
    with torch.inference_mode():
        next_token_logits = model.thinker(**inputs).logits[0, -1]
    yes_id, no_id = _get_answer_token_ids()
    yes_probability = torch.softmax(next_token_logits[[yes_id, no_id]].float(), dim=0)[0].item()
    is_yes = yes_probability >= 0.5
    confidence = yes_probability if is_yes else 1 - yes_probability
    return Verdict(is_yes, confidence)
