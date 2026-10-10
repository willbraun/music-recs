from pathlib import Path

import analyze
import pytest
import torch


@pytest.mark.parametrize(
    ("exploration", "expected"),
    [
        (0, analyze.STRICT_GUIDANCE),
        (33, analyze.STRICT_GUIDANCE),
        (34, analyze.BALANCED_GUIDANCE),
        (66, analyze.BALANCED_GUIDANCE),
        (67, analyze.OPEN_GUIDANCE),
        (100, analyze.OPEN_GUIDANCE),
    ],
)
def test_pick_guidance_by_exploration_level(exploration: int, expected: str) -> None:
    assert analyze._pick_guidance(exploration) == expected


def test_apply_rotary_time_emb_rotates_leading_dims_and_keeps_dtype(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analyze.modeling_musicflamingo, "rotate_half", lambda x: -x)
    hidden = torch.ones(1, 1, 4, dtype=torch.bfloat16)
    cos = torch.full((1, 1, 2), 2.0)
    sin = torch.full((1, 1, 2), 0.5)

    result = analyze.apply_rotary_time_emb(hidden, cos, sin)

    assert result.dtype == torch.bfloat16
    # Rotated dims: 1*2 + (-1)*0.5 = 1.5; the remaining dims pass through.
    assert result.tolist() == [[[1.5, 1.5, 1.0, 1.0]]]


class _FakeInputs(dict):
    def to(self, _device):
        return self


class _FakeProcessor:
    def __init__(self) -> None:
        self.conversation = None

    def apply_chat_template(self, conversation, **_kwargs) -> _FakeInputs:
        self.conversation = conversation
        return _FakeInputs(input_features=torch.zeros(1))


class _FakeModel:
    device = "cpu"
    dtype = torch.float32

    def __init__(self, yes_logit: float, no_logit: float) -> None:
        self._logits = torch.zeros(1, 1, 10)
        self._logits[0, -1, 1] = yes_logit
        self._logits[0, -1, 2] = no_logit

    def __call__(self, **_inputs):
        return type("Output", (), {"logits": self._logits})()


def _stub_model(monkeypatch: pytest.MonkeyPatch, yes_logit: float, no_logit: float) -> _FakeProcessor:
    processor = _FakeProcessor()
    monkeypatch.setattr(analyze, "_load", lambda: (processor, _FakeModel(yes_logit, no_logit)))
    monkeypatch.setattr(analyze, "_get_answer_token_ids", lambda: (1, 2))
    return processor


def test_analyze_reports_yes_with_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_model(monkeypatch, yes_logit=2.0, no_logit=0.0)

    assert analyze.analyze(Path("clip.wav"), "taste", 50) == "Verdict: YES (88% confidence)"


def test_analyze_reports_no_with_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_model(monkeypatch, yes_logit=0.0, no_logit=2.0)

    assert analyze.analyze(Path("clip.wav"), "taste", 50) == "Verdict: NO (88% confidence)"


def test_analyze_prompt_includes_taste_guidance_and_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    processor = _stub_model(monkeypatch, yes_logit=1.0, no_logit=0.0)

    analyze.analyze(Path("clip.wav"), "my taste", 0)

    text, audio = processor.conversation[0]["content"]
    assert "my taste" in text["text"]
    assert analyze.STRICT_GUIDANCE in text["text"]
    assert audio == {"type": "audio", "path": "clip.wav"}
