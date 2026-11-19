# Building the desktop app

`scripts/build.sh` builds the macOS (Apple Silicon) app and DMG. No Apple credentials are needed: without `APPLE_SIGNING_IDENTITY` the build is simply unsigned, which is fine for local use. Other Macs show a Gatekeeper warning for an unsigned app. Signing and notarization are only needed for distributable releases.

## Signing

The build signs the app with your Developer ID when `APPLE_SIGNING_IDENTITY` is set, either in the environment or in a git-ignored `.env` at the repo root. `scripts/sign-api.sh` signs the frozen API first, because Tauri does not sign resource files itself.

## Notarization

Notarization is opt-in, because it uploads the whole app to Apple. Set `NOTARIZE=1` and provide `APPLE_ID`, `APPLE_PASSWORD` (an app-specific password) and `APPLE_TEAM_ID`:

```
NOTARIZE=1 scripts/build.sh
```

Example `.env` (values with spaces must be quoted):

```
APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (TEAMID)"
APPLE_ID=you@example.com
APPLE_PASSWORD=xxxx-xxxx-xxxx-xxxx
APPLE_TEAM_ID=TEAMID
```

## Verifying a build

Use the paths under `frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/`:

- `codesign --verify --deep --strict --verbose=2 "macos/Music Recs.app"` checks the signature.
- `xcrun stapler validate "macos/Music Recs.app"` checks for a notarization ticket.
- `spctl -a -vv -t exec "macos/Music Recs.app"` shows Gatekeeper's verdict: `Notarized Developer ID` when notarized, `Unnotarized Developer ID` when only signed.
