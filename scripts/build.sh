#!/bin/bash
# Builds the macOS (Apple Silicon) desktop app: frontend, frozen API, then the Tauri bundle.
# Signs when APPLE_SIGNING_IDENTITY is set (from the environment or the git-ignored .env); notarizes only when NOTARIZE=1.
set -euo pipefail

# Get the root directory of the project, two levels up from this script
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Tauri runs `xattr -cr` when signing; a pip-installed xattr earlier on PATH rejects -r.
export PATH="/usr/bin:$PATH"

# Skips the Finder styling step of the dmg build, which fails with "Resource busy" for an app this large.
export CI=true

if [ -f "$ROOT/.env" ]; then
	set -a
	# shellcheck source=/dev/null
	source "$ROOT/.env"
	set +a
fi

# Tauri notarizes whenever it sees these, and the upload is slow, so require an explicit opt-in.
if [ "${NOTARIZE:-}" != "1" ]; then
	unset APPLE_ID APPLE_PASSWORD APPLE_TEAM_ID
fi

(cd "$ROOT/frontend" && npm run build)
(cd "$ROOT/api" && ../.venv/bin/pyinstaller --noconfirm music-recs-api.spec)

# The frozen API must be signed before Tauri copies it into the app and seals the bundle.
if [ -n "${APPLE_SIGNING_IDENTITY:-}" ]; then
	"$ROOT/scripts/sign-api.sh"
fi

(cd "$ROOT/frontend" && npm run tauri:build)

# Sign the Tauri app bundle if APPLE_SIGNING_IDENTITY is set
if [ -n "${APPLE_SIGNING_IDENTITY:-}" ]; then
	APP="$ROOT/frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/Music Recs.app"
	codesign --verify --deep --strict --verbose=2 "$APP"

	# Notarize the app if NOTARIZE=1 is set
	if [ "${NOTARIZE:-}" = "1" ]; then
		xcrun stapler validate "$APP"
		spctl -a -vv -t exec "$APP"
	else
		echo "Signed but not notarized (set NOTARIZE=1 to notarize)."
	fi
fi
