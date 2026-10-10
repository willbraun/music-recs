import wave
from pathlib import Path

import embed
import numpy as np
import pytest
import torch


def _write_wav(path: Path, seconds: int, rate: int = embed.SAMPLE_RATE, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.zeros(seconds * rate * channels, dtype="<i2").tobytes())


class _FakeModel:
    def __init__(self, latents: list[list[float]]) -> None:
        self.latents = torch.tensor(latents)
        self.calls: list[dict] = []

    def __call__(self, wavs=None, texts=None) -> torch.Tensor:
        self.calls.append({"wavs": wavs, "texts": texts})
        return self.latents


def test_embed_audio_embeds_each_ten_second_window_and_averages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clip = tmp_path / "clip.wav"
    _write_wav(clip, 40)
    # Window norms differ, so each must be normalized before averaging.
    model = _FakeModel([[10, 0], [0, 1], [0, 1], [10, 0]])
    monkeypatch.setattr(embed, "_load", lambda: (model, "cpu"))

    result = embed.embed_audio(clip)

    assert model.calls[0]["wavs"].shape == (4, 10 * embed.SAMPLE_RATE)
    assert result.dtype == np.float32
    assert np.allclose(result, [np.sqrt(0.5), np.sqrt(0.5)])
    assert np.isclose(np.linalg.norm(result), 1.0)


def test_embed_audio_uses_one_window_for_a_short_clip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clip = tmp_path / "clip.wav"
    _write_wav(clip, 4)
    model = _FakeModel([[3, 4]])
    monkeypatch.setattr(embed, "_load", lambda: (model, "cpu"))

    result = embed.embed_audio(clip)

    assert model.calls[0]["wavs"].shape == (1, 4 * embed.SAMPLE_RATE)
    assert np.allclose(result, [0.6, 0.8])


@pytest.mark.parametrize(("rate", "channels"), [(44100, 1), (embed.SAMPLE_RATE, 2)])
def test_embed_audio_rejects_unexpected_wav_formats(tmp_path: Path, rate: int, channels: int) -> None:
    clip = tmp_path / "clip.wav"
    _write_wav(clip, 1, rate=rate, channels=channels)

    with pytest.raises(ValueError):
        embed.embed_audio(clip)


def test_embed_text_returns_one_normalized_row_per_phrase(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _FakeModel([[3, 4], [0, 2]])
    monkeypatch.setattr(embed, "_load", lambda: (model, "cpu"))

    result = embed.embed_text(["a", "b"])

    assert model.calls[0]["texts"] == ["a", "b"]
    assert np.allclose(result, [[0.6, 0.8], [0, 1]])
