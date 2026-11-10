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

# MLX looks for mlx.metallib beside the libmlx.dylib it loaded; PyInstaller loads the copy at the bundle root.
datas.append((os.path.join(get_package_paths("mlx")[1], "lib", "mlx.metallib"), "."))

# yt-dlp imports its extractors by name.
hiddenimports += collect_submodules("yt_dlp")

analysis = Analysis(["api.py"], datas=datas, binaries=binaries, hiddenimports=hiddenimports)
pyz = PYZ(analysis.pure)

# onedir: a onefile build would re-extract the large MLX stack on every launch.
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="music-recs-api", console=True)
coll = COLLECT(exe, analysis.binaries, analysis.datas, name="music-recs-api")
