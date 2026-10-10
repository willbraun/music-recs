from functools import lru_cache
from pathlib import Path

import torch
from transformers import AutoProcessor, MusicFlamingoForConditionalGeneration
from transformers.models.musicflamingo import modeling_musicflamingo

MODEL_ID = "nvidia/music-flamingo-2601-hf"
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


# MPS has no float64 support, so the upstream rotary embedding is redone in float32.
def apply_rotary_time_emb(hidden_states, cos, sin):
    original_dtype = hidden_states.dtype
    hidden_states = hidden_states.to(torch.float32)
    cos = cos.to(hidden_states)
    sin = sin.to(hidden_states)
    rot_dim = cos.shape[-1]

    passthrough = hidden_states[..., rot_dim:]
    rotated = hidden_states[..., :rot_dim]
    rotated = (rotated * cos) + (modeling_musicflamingo.rotate_half(rotated) * sin)
    return torch.cat((rotated, passthrough), dim=-1).to(original_dtype)


modeling_musicflamingo.apply_rotary_time_emb = apply_rotary_time_emb


@lru_cache(maxsize=1)
def _load():
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    model = MusicFlamingoForConditionalGeneration.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map=device)
    return processor, model


@lru_cache(maxsize=1)
def _get_answer_token_ids() -> tuple[int, int]:
    tokenizer = _load()[0].tokenizer
    yes_id, no_id = (tokenizer.encode(word, add_special_tokens=False)[0] for word in ("YES", "NO"))
    return yes_id, no_id


def analyze(audio_path: Path, taste: str, exploration: int) -> str:
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
    ).to(model.device)
    inputs["input_features"] = inputs["input_features"].to(model.dtype)

    # Compute the probability of the next token being YES or NO and determine the verdict.
    with torch.inference_mode():
        next_token_logits = model(**inputs).logits[0, -1]
    yes_id, no_id = _get_answer_token_ids()
    yes_probability = torch.softmax(next_token_logits[[yes_id, no_id]].float(), dim=0)[0].item()
    is_yes = yes_probability >= 0.5
    confidence = yes_probability if is_yes else 1 - yes_probability
    return f"Verdict: {'YES' if is_yes else 'NO'} ({confidence:.0%} confidence)"
