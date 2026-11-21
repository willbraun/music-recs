# Building the desktop app

`scripts/build.sh` builds the macOS (Apple Silicon) app and DMG. No Apple credentials are needed: without `APPLE_SIGNING_IDENTITY` the build is simply unsigned, which is fine for local use. Other Macs show a Gatekeeper warning for an unsigned app. Signing and notarization are only needed for distributable releases.

## Setup

The build expects a Python virtual environment at the repo root and the frontend packages installed:

```
python3 -m venv .venv
.venv/bin/pip install -r api/requirements.lock
npm ci --prefix frontend
```

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

## Python dependencies

`api/requirements.txt` and `api/requirements-dev.txt` list the top-level packages. `api/requirements.lock` pins every package (a `pip freeze`), and CI and releases install from it. To update dependencies:

1. Upgrade in your `.venv`, for example `pip install -U mlx-audio mlx-lm`.
2. Run `cd api && python -m pytest` and an unsigned `scripts/build.sh`, then launch the app.
3. Run `.venv/bin/pip freeze > api/requirements.lock` and commit it.

`model_download.py` relies on `huggingface_hub` 2.2.0 internals, so only upgrade it together with that code.

## Releasing

`.github/workflows/ci.yml` runs lint, type checks, tests and an unsigned build on every push to `main` and every pull request.

`.github/workflows/release.yml` builds, signs and notarizes the app, then publishes a GitHub Release:

1. Bump `version` in `frontend/src-tauri/Cargo.toml` (and `Cargo.lock`), and merge it to `main`.
2. In GitHub, open Actions > Release > Run workflow on `main`, and enter the version with a leading `v`, for example `v0.1.0`. The `X.Y.Z` part must match the `version` in `Cargo.toml`, which has no `v`. For a test run, enter a suffixed version such as `v0.1.0-rc1` and check `prerelease`; the suffix is ignored when matching `Cargo.toml`, so no version bump is needed.
3. The workflow creates the tag and a release with generated notes, the dmg and its sha256.

Signing secrets live only in the `production-release` environment (Settings > Environments), never in repository secrets, so CI cannot read them:

- `APPLE_CERTIFICATE`: the Developer ID Application certificate and private key exported as a `.p12`, base64-encoded (`base64 -i cert.p12`)
- `APPLE_CERTIFICATE_PASSWORD`: the `.p12` password
- `APPLE_SIGNING_IDENTITY`: for example `Developer ID Application: Your Name (TEAMID)`
- `APPLE_ID`, `APPLE_PASSWORD` (app-specific password), `APPLE_TEAM_ID`: for notarization
