import os
import sys
from pathlib import Path

# The desktop app (Tauri) configures the frozen API through these variables; unset they fall back to the dev layout.
DATA_DIR_ENV = "MUSIC_RECS_DATA_DIR"
FRONTEND_DIR_ENV = "MUSIC_RECS_FRONTEND_DIR"
PORT_ENV = "MUSIC_RECS_PORT"
DEFAULT_PORT = 8000

IS_FROZEN = getattr(sys, "frozen", False)
# Bundled data files live in PyInstaller's extraction dir when frozen.
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))


def get_data_dir() -> Path:
    # The install directory is read-only once packaged, so user data goes to a configurable directory.
    configured = os.environ.get(DATA_DIR_ENV)
    if configured is None:
        return Path(__file__).parent
    path = Path(configured)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_frontend_dir() -> Path | None:
    # Dev serves the frontend with Vite, so the API only serves it when told to or when frozen.
    configured = os.environ.get(FRONTEND_DIR_ENV)
    if configured is not None:
        return Path(configured)
    return RESOURCE_DIR / "frontend" if IS_FROZEN else None


def get_port() -> int:
    return int(os.environ.get(PORT_ENV, DEFAULT_PORT))


def get_ffmpeg_path() -> str | None:
    """Bundled ffmpeg from imageio-ffmpeg; None falls back to ffmpeg on PATH."""
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    return imageio_ffmpeg.get_ffmpeg_exe()
