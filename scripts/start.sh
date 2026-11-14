#!/bin/bash

# Get the root directory of the project, two levels up from this script
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Ctrl-C or exit stops both servers.
trap 'kill $API_PID $FRONTEND_PID 2>/dev/null' EXIT INT TERM

# Start the API server
(cd "$ROOT/api" && exec ../.venv/bin/python api.py) &
API_PID=$!
while ! nc -z localhost 8000; do
  sleep 1
done

# Start the frontend development server
(cd "$ROOT/frontend" && exec npm run dev) &
FRONTEND_PID=$!
while ! nc -z localhost 5173; do
  sleep 1
done

# Open new Safari window, since Tauri uses WebKit
osascript -e 'tell application "Safari"
  activate
  make new document with properties {URL:"http://localhost:5173"}
end tell' || echo "Failed to open Safari window. Please open manually."

wait