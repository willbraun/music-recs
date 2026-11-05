from pathlib import Path

import analyze
import mlx.core as mx
import pytest


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


class _FakeProcessor:
    def __init__(self) -> None:
        self.call = None

    def __call__(self, *, text, audio):
        self.call = {"text": text, "audio": audio}
        return "processed"


class _FakeModel:
    def __init__(self, yes_logit: float, no_logit: float) -> None:
        logits = [0.0] * 10
        logits[1], logits[2] = yes_logit, no_logit
        self._logits = mx.array([[logits]])
        self.processor = _FakeProcessor()

    def _ensure_processor(self) -> _FakeProcessor:
        return self.processor

    def _build_prompt_embeddings(self, processed):
        assert processed == "processed"
        return mx.zeros(1, dtype=mx.int32), mx.zeros((1, 1, 1)), None, 1

    def __call__(self, _ids, **_kwargs):
        return self._logits


def _stub_model(monkeypatch: pytest.MonkeyPatch, yes_logit: float, no_logit: float) -> _FakeProcessor:
    model = _FakeModel(yes_logit, no_logit)
    monkeypatch.setattr(analyze, "_load", lambda: model)
    monkeypatch.setattr(analyze, "_get_answer_token_ids", lambda: (1, 2))
    return model.processor


def test_analyze_reports_yes_with_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_model(monkeypatch, yes_logit=2.0, no_logit=0.0)

    verdict = analyze.analyze(Path("clip.wav"), "taste", 50)

    assert verdict.recommended is True
    assert verdict.confidence == pytest.approx(0.8808, abs=1e-4)


def test_analyze_reports_no_with_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_model(monkeypatch, yes_logit=0.0, no_logit=2.0)

    verdict = analyze.analyze(Path("clip.wav"), "taste", 50)

    assert verdict.recommended is False
    assert verdict.confidence == pytest.approx(0.8808, abs=1e-4)


def test_analyze_prompt_includes_taste_guidance_and_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    processor = _stub_model(monkeypatch, yes_logit=1.0, no_logit=0.0)

    analyze.analyze(Path("clip.wav"), "my taste", 0)

    assert "my taste" in processor.call["text"]
    assert analyze.STRICT_GUIDANCE in processor.call["text"]
    assert processor.call["audio"] == "clip.wav"
