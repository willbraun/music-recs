# PyInstaller spec; build from api/ with `pyinstaller music-recs-api.spec` after `npm run build` in frontend/.
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules, get_package_paths

datas = [("migrations", "migrations"), ("../frontend/build", "frontend")]
binaries = []
hiddenimports = ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.lifespan.on"]

# These load native libraries, model code, or plugins dynamically, so static analysis misses them.
for package in ("mlx", "mlx_audio", "mlx_lm", "imageio_ffmpeg", "huggingface_hub", "transformers", "tokenizers"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

# C++ headers and CMake files are only for building MLX extensions.
datas = [(src, dest) for src, dest in datas if not dest.startswith(("mlx/include", "mlx/share", "mlx/lib/cmake"))]

# Tauri copies bundle resources without symlinks, so the app loads the root libmlx.dylib and MLX looks for the metallib beside it.
datas = [(src, dest) for src, dest in datas if os.path.basename(src) != "mlx.metallib"]
datas.append((os.path.join(get_package_paths("mlx")[1], "lib", "mlx.metallib"), "."))

# yt-dlp imports its extractors by name.
hiddenimports += collect_submodules("yt_dlp")

# Unused by the app, but transformers and mlx-audio probe for them and PyInstaller bundles whatever is installed.
excludes = [
    "torch", "torchaudio", "torchvision", "torchgen", "functorch", "accelerate",
    "numba", "llvmlite", "librosa", "sklearn", "matplotlib", "pandas", "IPython", "pytest", "tkinter",
    "muq", "laya", "x_clip", "nnaudio",
]

analysis = Analysis(["api.py"], datas=datas, binaries=binaries, hiddenimports=hiddenimports, excludes=excludes)
pyz = PYZ(analysis.pure)

# onedir: a onefile build would re-extract the large MLX stack on every launch.
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="music-recs-api", console=True)
coll = COLLECT(exe, analysis.binaries, analysis.datas, name="music-recs-api")
