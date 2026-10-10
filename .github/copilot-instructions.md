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

The frontend should provide a responsive, polished interface for discovering recommendations, browsing songs, listening to music, and providing feedback.

## Source of Truth

Follow these sources in order of precedence:

1. **Feature specifications:** Files in `specs/` define the intended behavior and acceptance criteria.
2. **Project instructions:** This file defines architectural conventions and implementation constraints.
3. **Existing backend contracts:** The Python API and SQLite schema define existing integration boundaries unless a spec explicitly requires changes.
4. **Legacy frontend:** Existing HTML, CSS, and JavaScript are reference material for appearance and existing user flows only. They are not the source of truth for the new implementation.

If requirements conflict or a specification is ambiguous, identify the conflict before making assumptions that affect architecture, data contracts, or user-visible behavior.

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
- Keep frontend code compatible with the intended deployment model. Do not introduce server-side dependencies or browser-only assumptions without considering where the code executes.
- Avoid duplicating business logic that already belongs in the Python backend.

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

- Use the legacy frontend and screenshots as visual references, not implementation templates.
- Follow the design specifications in `specs/`.
- Maintain consistent spacing, typography, colors, component behavior, and interaction patterns.
- Make the interface responsive to different screen sizes.
- Provide clear feedback for loading operations, failures, and user actions.
- Avoid unnecessary navigation, dialogs, animations, or visual complexity.
- Ensure interactive elements have appropriate accessible labels, keyboard support, and focus states.
- Preserve existing functionality only when it is required by the specifications or explicitly requested.

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

- Review relevant specifications and existing tests before making changes.
- Implement frontend unit tests using Vitest and Svelte Testing Library.
- Add or update tests for new behavior and bug fixes where practical.
- Test important success, failure, empty, and loading states.
- Run the available tests, type checks, and linting commands after making changes.
- Verify that frontend changes remain compatible with the existing Python API.
- Do not claim that tests passed unless they were actually executed successfully.
- Report any checks that could not be run.

## Working with Specifications

- Read the relevant specification before implementing a feature.
- Treat acceptance criteria as requirements, not optional suggestions.
- If a task is too large, break it into small, independently verifiable steps.
- If implementation reveals missing requirements, document the ambiguity and propose a resolution.
- Update specifications when explicitly requested or when an agreed behavior changes.
- When there are database updates, update the specs/database.md and ensure any relevant migration scripts or cache handling logic are also reviewed and updated accordingly. Schema changes are a new numbered file in `api/migrations/`; never edit a migration that has been applied.
- Do not silently change the intended product behavior to make implementation easier.

## Legacy Frontend Migration

- Do not mechanically translate the existing HTML, CSS, and JavaScript into Svelte components.
- Reimplement behavior using SvelteKit conventions and the feature specifications.
- Reuse visual assets, styling ideas, and design decisions when appropriate.
- Avoid carrying over legacy workarounds, unnecessary complexity, or direct DOM manipulation.
- Keep the legacy implementation unchanged unless explicitly asked to modify it.
- Do not delete legacy files until the replacement has been validated and their removal has been approved.

## Git and Change Management

- Keep changes focused and reviewable.
- Do not overwrite unrelated user changes.
- Do not discard work, reset branches, or run destructive commands without explicit authorization.
- Do not commit, push, or deploy unless requested.
- Summarize the files changed, behavior implemented, and validation performed when completing a task.

## Definition of Done

A task is complete when:

- The implementation matches the relevant specification.
- The code follows the project's architectural conventions.
- Relevant tests and checks have been run.
- Existing backend integration contracts remain intact unless explicitly changed.
- Important errors, assumptions, and outstanding issues are documented.
