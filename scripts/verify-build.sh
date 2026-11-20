#!/bin/bash
# Verifies the built app's signature, notarization ticket and Gatekeeper verdict (see BUILDING.md).
# Each check runs even if an earlier one fails, since an unnotarized build is expected to fail the last two.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLE="$ROOT/frontend/src-tauri/target/aarch64-apple-darwin/release/bundle"
APP="macos/Music Recs.app"

cd "$BUNDLE" || { echo "Bundle directory not found: $BUNDLE" >&2; exit 1; }

status=0

echo "==> [1/3] Code signature: checking the app and everything nested in it is validly signed (codesign)"
codesign --verify --deep --strict --verbose=2 "$APP" || status=1

echo
echo "==> [2/3] Notarization ticket: checking Apple's notarization ticket is stapled to the app (stapler)"
xcrun stapler validate "$APP" || status=1

echo
echo "==> [3/3] Gatekeeper verdict: checking macOS would allow the app to run (spctl)"
spctl -a -vv -t exec "$APP" || status=1

exit $status
