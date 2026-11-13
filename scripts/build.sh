#!/bin/bash
# Builds the macOS (Apple Silicon) desktop app: frontend, frozen API, then the Tauri bundle.
set -euo pipefail

# Get the root directory of the project, two levels up from this script
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Skips the Finder styling step of the dmg build, which fails with "Resource busy" for an app this large.
export CI=true

(cd "$ROOT/frontend" && npm run build)
(cd "$ROOT/api" && ../.venv/bin/pyinstaller --noconfirm music-recs-api.spec)
(cd "$ROOT/frontend" && npm run tauri:build)
