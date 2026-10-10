import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

MODEL_ID = "OpenMuQ/MuQ-MuLan-large"
SAMPLE_RATE = 24000
WINDOW_SECONDS = 10


@lru_cache(maxsize=1)
def _load():
    from muq import MuQMuLan

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    return MuQMuLan.from_pretrained(MODEL_ID).to(device).eval(), device


def _normalize(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)


def _read_wav(path: Path) -> np.ndarray:
    # The clip is written as 24 kHz mono 16-bit PCM by the download step, so no resampling is needed.
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"{path} must be 24 kHz mono 16-bit WAV")
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def _split_windows(audio: np.ndarray) -> np.ndarray:
    size = WINDOW_SECONDS * SAMPLE_RATE
    count = max(1, len(audio) // size)
    return np.stack([audio[i * size : (i + 1) * size] for i in range(count)])


def embed_audio(path: Path) -> np.ndarray:
    """Embed a clip as the normalized mean of its normalized 10 second window embeddings."""
    windows = _split_windows(_read_wav(path))
    model, device = _load()
    windows = torch.from_numpy(windows).to(device)
    with torch.inference_mode():
        latents = model(wavs=windows).float().cpu().numpy()
    return _normalize(_normalize(latents).mean(axis=0)).astype(np.float32)


def embed_text(phrases: list[str]) -> np.ndarray:
    """Embed each phrase into the audio space; returns one normalized row per phrase."""
    model, _ = _load()
    with torch.inference_mode():
        latents = model(texts=phrases).float().cpu().numpy()
    return _normalize(latents).astype(np.float32)
