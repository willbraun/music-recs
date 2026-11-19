#!/bin/bash
# Signs every Mach-O file in the PyInstaller output; Tauri copies it into the app as a resource but does not sign it.
# Needs APPLE_SIGNING_IDENTITY. Libraries are signed before the executables that load them.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/api/dist/music-recs-api"
ENTITLEMENTS="$ROOT/api/entitlements.plist"

: "${APPLE_SIGNING_IDENTITY:?APPLE_SIGNING_IDENTITY must be set}"

# PyInstaller links _internal/Python into Python.framework, and Tauri copies resources without symlinks, which leaves a malformed framework.
# Its Info.plist-bound signature is then invalid at one location or the other, so keep one real Python library and drop the framework.
if [ -d "$DIST/_internal/Python.framework" ]; then
	cp -pL "$DIST/_internal/Python" "$DIST/_internal/Python.real"
	rm -rf "$DIST/_internal/Python" "$DIST/_internal/Python.framework"
	mv "$DIST/_internal/Python.real" "$DIST/_internal/Python"
fi

# Mach-O files are found by content: Python and the bundled ffmpeg have no .so/.dylib extension. Symlinks are skipped.
LIBRARIES=()
EXECUTABLES=()
while IFS= read -r -d '' path; do
	description="$(file -b "$path")"
	case "$description" in
		*"Mach-O"*"executable"*) EXECUTABLES+=("$path") ;;
		*"Mach-O"*) LIBRARIES+=("$path") ;;
	esac
done < <(find "$DIST" -type f -print0)

echo "Signing ${#LIBRARIES[@]} libraries and ${#EXECUTABLES[@]} executables"

sign() {
	codesign --force --timestamp --options runtime --sign "$APPLE_SIGNING_IDENTITY" "$@"
}

if [ "${#LIBRARIES[@]}" -gt 0 ]; then
	printf '%s\0' "${LIBRARIES[@]}" | xargs -0 -n 20 -P 4 codesign --force --timestamp --options runtime --sign "$APPLE_SIGNING_IDENTITY"
fi

for path in "${EXECUTABLES[@]}"; do
	sign --entitlements "$ENTITLEMENTS" "$path"
done

for path in "${LIBRARIES[@]}" "${EXECUTABLES[@]}"; do
	codesign --verify --strict "$path"
done
echo "Signed and verified $((${#LIBRARIES[@]} + ${#EXECUTABLES[@]})) files"
