# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- Require the complete motion schema v2 contract and reject older schema versions.
- Make ordered render-frame entries authoritative and remove redundant render counts and duration arrays.
- Validate render timing density, resource limits, encoded WebP durations, and integer pixel-art scaling.
- Centralize validation-report evidence checks and bind export validation to unchanged upstream reports.
- Add one read-only doctor command with deep media checks, three-state results, and versioned JSON output.
- Add a synthetic golden workflow fixture covering keyframe and render-track exports plus invalidation chains.
- Add one offline HTML review generator for package, render-track, and export reports.
- Make Review Page playback control the actual decoded WebP/GIF target, move semantic hold to timeline evidence, and pair true-size with zoomed 50×50 inspection.
- Add agent-selected Chinese/English Review Page localization and explain the semantic-hold marker inline.
- Remove unused cover artwork and consolidate repeated integrity helpers.
- Add Validation Report schema v1 and accept only the current motion/report formats without compatibility migration.
- Keep nonstandard package checks factual and record allowed deviations separately as policy overrides.
- Replace GIF, preview, and export report transactionally so failed exports preserve the previous validated set.
- Write visual-validation updates atomically and keep Review HTML free of absolute host paths.
- Split Review media/assets, GIF export stages, and Doctor checks into focused runtime modules while preserving the public CLI behavior.

## [0.8.1] - 2026-07-16

- Keep development-only tests outside the installable Skill so `npx skills add` and ClawHub distribute only runtime files.

## [0.8.0] - 2026-07-16

- Publish the generic single-sticker workflow as a standalone Agent Skills repository.
- Use one portable `SKILL.md` with optional OpenAI interface metadata.
- Add reference-image metadata, transactional packaging, and artifact fingerprints.
- Separate `technical_validation` from maker-side `visual_validation` and require `deliverable_ready` for delivery.
- Add an optional numeric-FPS render track while keeping authored semantic keyframes as the default.
- Add adaptive GIF export with palette and frame-rate fallback policies.
- Add Apache-2.0 licensing, Python 3.10–3.13 CI, and cross-agent `npx skills add` installation guidance.
