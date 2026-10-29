---
description: This file contains project instructions for the development workflow and coding standards.
applyTo: **
---

# Copilot Instructions

## Project Overview

<!-- Describe what the application does and who it is for. -->

This project is a music recommendation application that analyzes songs and recommends music based on the user's listening preferences.

The application consists of:

- A SvelteKit frontend built with TypeScript.
- An existing Python API responsible for backend functionality and music analysis.
- A SQLite database for persistent application data.

The frontend should provide a responsive, polished interface for discovering recommendations, browsing songs, and listening to music.

## Where Things Live

The code and its comments are the only source of truth. Start from these files:

- **API contract:** `api/api.py` (endpoints, request validation, error codes, run event stream).
- **Run pipeline and event shapes:** `api/pipeline.py`.
- **Schema and persistence:** `api/migrations/` and `api/appdb.py`.
- **Taste rules and rendering:** `api/taste_profile.py`.
- **Artwork lookup:** `api/artwork.py`.
- **Frontend API client and payload types:** `frontend/src/lib/api.ts`.
- **Frontend shared state (survives navigation):** `frontend/src/lib/*.svelte.ts` (`player`, `run`, `taste`).
- **Routes:** `frontend/src/routes/` (`/` Home, `/songs`, `/taste`).

Development runs the API on `127.0.0.1:8000` and the Vite dev server on `localhost:5173`, which proxies `/api`. `start.sh` starts both. The API does not serve the frontend.

## Source of Truth

Follow these sources in order of precedence:

1. **The code and its comments:** Existing behavior, data contracts, and rationale are defined by the implementation, its tests, and the comments next to it.
2. **Project instructions:** This file defines architectural conventions and implementation constraints.
3. **The user's request:** A task may deliberately change existing behavior. Confirm before changing API contracts, the database schema, or user-visible behavior beyond what was asked.

If the code, its comments, and the request conflict or are ambiguous, identify the conflict before making assumptions that affect architecture, data contracts, or user-visible behavior.

## General Development Principles

- Prefer simple, maintainable solutions over unnecessary abstractions.
- Follow established conventions and patterns in the current codebase.
- Avoid introducing dependencies unless they provide clear value.
- Make focused changes that address the current task.
- Do not rewrite unrelated code or perform unnecessary refactoring.
- Do not introduce placeholder functionality that appears complete but does not work.
- Do not silently remove existing functionality.
- Explain important architectural decisions and trade-offs when proposing changes.

## Frontend Architecture

- Use SvelteKit with TypeScript.
- Use idiomatic Svelte components, reactive state, and event handling.
- Avoid direct DOM manipulation when Svelte provides a suitable declarative approach.
- Keep components focused on a clear responsibility.
- Extract shared components when doing so improves consistency or maintainability.
- Separate UI presentation, application logic, and API communication where appropriate.
- Use SvelteKit routing conventions rather than adding a separate router without an explicit need.
- Keep frontend code compatible with the intended deployment model: a client-only SPA (`ssr = false`) that talks to the Python API through relative `/api` URLs. Do not introduce server-side dependencies or browser-only assumptions without considering where the code executes.
- Avoid duplicating business logic that already belongs in the Python backend.
- If there are problems in the editor with Svelte files, feel free to restart the Svelte Language server to resolve them.

## Backend and Data Integration

- Treat the existing Python API as the primary interface between the frontend and backend.
- Inspect existing API endpoints, request/response formats, and error handling before implementing integrations.
- Reuse existing endpoints and data structures whenever possible.
- Do not access SQLite directly from the frontend.
- Do not change database schemas, API contracts, or backend behavior without a clear requirement.
- Handle loading, empty, success, and error states explicitly.
- Keep API communication in reusable modules rather than duplicating fetch logic throughout components.
- Do not hardcode data that should come from the API or database.

## UI and UX

- Reuse the existing components and styling (shadcn-svelte and Tailwind) rather than introducing new visual patterns.
- Maintain consistent spacing, typography, colors, component behavior, and interaction patterns.
- Make the interface responsive to different screen sizes.
- Provide clear feedback for loading operations, failures, and user actions.
- Avoid unnecessary navigation, dialogs, animations, or visual complexity.
- Ensure interactive elements have appropriate accessible labels, keyboard support, and focus states.
- Preserve existing functionality unless a change is explicitly requested.

## Code Quality

- Use TypeScript types for application data, component props, and API responses.
- Avoid `any` unless there is a documented reason it is necessary.
- All functions should use a verb in their name to clearly indicate the action they perform.
- Handle asynchronous operations and errors deliberately.
- Avoid duplicated logic and deeply coupled components.
- Use descriptive names for variables, functions, components, and files.
- Keep secrets, credentials, and machine-specific configuration out of source control.
- Follow existing formatting, linting, and naming conventions.

## Testing and Validation

- Read the relevant code, comments, and existing tests before making changes.
- Implement frontend unit tests using Vitest and Svelte Testing Library.
- Add or update tests for new behavior and bug fixes where practical.
- Test important success, failure, empty, and loading states.
- Run the available tests, type checks, and linting commands after making changes.
- Verify that frontend changes remain compatible with the existing Python API.
- Do not claim that tests passed unless they were actually executed successfully.
- Report any checks that could not be run.

## Working with the Code as the Source of Truth

- Read the code that owns a behavior before changing it, including its comments and tests.
- If a task is too large, break it into small, independently verifiable steps.
- If implementation reveals missing requirements, document the ambiguity and propose a resolution.
- When behavior, a contract, or a rule changes, update the nearby comments and tests in the same change so they do not go stale.
- Comments state only what the code cannot show, such as rationale, constraints, and contracts. Keep them to one short line.
- When there are database updates, review the relevant migration scripts and `AppDb` methods. Schema changes are a new timestamped file (`YYYYMMDDHHMMSS_name.sql`) in `api/migrations/`; never edit a migration that has been applied.
- Do not silently change the intended product behavior to make implementation easier.

## Git and Change Management

- Keep changes focused and reviewable.
- Do not overwrite unrelated user changes.
- Do not discard work, reset branches, or run destructive commands without explicit authorization.
- Do not commit, push, or deploy unless requested.
- Summarize the files changed, behavior implemented, and validation performed when completing a task.

## Definition of Done

A task is complete when:

- The implementation does what was requested and is consistent with the surrounding code and its comments.
- The code follows the project's architectural conventions.
- Relevant tests and checks have been run.
- Existing backend integration contracts remain intact unless explicitly changed.
- Important errors, assumptions, and outstanding issues are documented.
