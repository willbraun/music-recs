from pathlib import Path

import paths
import pytest


def test_data_dir_defaults_to_the_api_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)

    assert paths.get_data_dir() == Path(paths.__file__).parent


def test_data_dir_is_created_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "nested" / "data"
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(target))

    assert paths.get_data_dir() == target
    assert target.is_dir()


def test_frontend_dir_is_only_served_when_configured_or_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.FRONTEND_DIR_ENV, raising=False)
    monkeypatch.setattr(paths, "IS_FROZEN", False)
    assert paths.get_frontend_dir() is None

    monkeypatch.setattr(paths, "IS_FROZEN", True)
    assert paths.get_frontend_dir() == paths.RESOURCE_DIR / "frontend"

    monkeypatch.setenv(paths.FRONTEND_DIR_ENV, str(tmp_path))
    assert paths.get_frontend_dir() == tmp_path


def test_port_defaults_and_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.PORT_ENV, raising=False)
    assert paths.get_port() == paths.DEFAULT_PORT

    monkeypatch.setenv(paths.PORT_ENV, "51234")
    assert paths.get_port() == 51234


def test_ffmpeg_path_points_at_the_bundled_binary() -> None:
    path = paths.get_ffmpeg_path()

    assert path is not None
    assert Path(path).is_file()
