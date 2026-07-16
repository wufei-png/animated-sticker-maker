# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- Require the complete motion schema v2 contract and reject older schema versions.
- Make ordered render-frame entries authoritative and remove redundant render counts and duration arrays.
- Validate render timing density, resource limits, encoded WebP durations, and integer pixel-art scaling.
- Centralize validation-report evidence checks and bind export validation to unchanged upstream reports.
- Remove unused cover artwork and consolidate repeated integrity helpers.

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
