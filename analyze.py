from functools import lru_cache
from pathlib import Path

import torch
from transformers import AutoProcessor, MusicFlamingoForConditionalGeneration
from transformers.models.musicflamingo import modeling_musicflamingo

MODEL_ID = "nvidia/music-flamingo-2601-hf"
PROMPT = "You are an expert music recommender. Evaluate whether you would recommend the given song to me based on my musical taste. My taste is:"
OUTPUT_FORMAT = (
    "Respond in exactly this format. Response should have a maximum of 100 words. Line 1: 'Verdict: YES' or 'Verdict: NO' (YES only if I would like this song). "
    "Line 2: one sentence explaining why."
)
MAX_NEW_TOKENS = 256

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
    model = MusicFlamingoForConditionalGeneration.from_pretrained(MODEL_ID, device_map="auto")
    return processor, model


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

    outputs = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
    return processor.batch_decode(outputs[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
