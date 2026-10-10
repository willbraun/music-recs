import sys

import main
import pytest


class _FakeAppDb:
    def __init__(self, taste: object = "taste") -> None:
        self._taste = taste

    def get_current_taste(self) -> object:
        return self._taste


def _run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str], events: list[dict], taste: object = "taste") -> dict:
    captured: dict = {}
    appdb = _FakeAppDb(taste)

    def fake_run(query, count, exploration, appdb):
        captured.update(query=query, count=count, exploration=exploration, appdb=appdb)
        yield from events

    monkeypatch.setattr(main, "run", fake_run)
    monkeypatch.setattr(main, "AppDb", lambda: appdb)
    monkeypatch.setattr(sys, "argv", ["main.py", *argv])
    main.main()
    captured["fake_appdb"] = appdb
    return captured


def test_main_uses_defaults_without_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _run_main(monkeypatch, [], [])

    assert captured == {
        "query": None,
        "count": 3,
        "exploration": 50,
        "appdb": captured["fake_appdb"],
        "fake_appdb": captured["fake_appdb"],
    }


def test_main_passes_arguments_to_run(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _run_main(monkeypatch, ["daft punk", "--count", "5", "--exploration", "80"], [])

    assert (captured["query"], captured["count"], captured["exploration"]) == ("daft punk", 5, 80)


def test_main_rejects_out_of_range_exploration(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, ["--exploration", "101"], [])


def test_main_exits_without_a_taste(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    captured = _run_main(monkeypatch, [], [], taste=None)

    assert captured == {"fake_appdb": captured["fake_appdb"]}
    assert "No taste set. Open the app to set one." in capsys.readouterr().out


def test_main_prints_progress_and_recommendations(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    scored = {"artist": "A", "title": "T", "url": "http://u"}
    events = [
        {"type": "started"},
        {"type": "downloading_model", "model": "org/model"},
        {"type": "queries", "queries": [{"query": "flume", "tier": "familiar"}]},
        {"type": "seeding", "artist": "Flume"},
        {"type": "fetching"},
        {"type": "analyzing", "index": 1, "recommended_count": 0, "artist": "A", "title": "T"},
        {"type": "scored", "recommended": True, **scored},
        {"type": "scored", "recommended": False, "artist": "B", "title": "Nope", "url": "http://n"},
        {"type": "done", "analyzed": 2, "recommended": 1, "count": 3},
    ]

    _run_main(monkeypatch, [], events)

    out = capsys.readouterr().out
    assert "Downloading model org/model..." in out
    assert "Query (familiar): flume" in out
    assert "Learning songs by Flume..." in out
    assert "Fetching songs..." in out
    assert "Analyzed 1 songs; 0/3 recommended: A - T" in out
    assert "Recommended (1 of 3 requested; analyzed 2 songs):" in out
    assert "  A - T  http://u" in out
    assert "Nope" not in out
