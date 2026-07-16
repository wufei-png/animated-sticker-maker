# Validation

Validation is part of making the artifact, not an approval workflow and not a separate reviewer role. Run every applicable check before declaring a package or export deliverable.

## Deterministic diagnosis

Use `scripts/doctor.py` to re-run the deterministic checks available from an existing motion plan, package, validation report, or export. Doctor is read-only, aggregates independent findings, and does not create, repair, or visually approve artifacts.

- `healthy` means every applicable deterministic check and completed validation gate passes.
- `incomplete` means structure and technical evidence are valid, but an applicable visual validation is still pending.
- `invalid` means schema, media, paths, bindings, technical validation, or an explicit visual result failed.

Run doctor on the exact report before delivery. A package diagnosis aggregates its primary report and every declared render-track report, but does not recursively diagnose platform exports.

## Visual review page

Use `scripts/generate_review.py` when an exact report reaches visual validation and its artifact is intended for delivery. The page is one read-only, offline visual language that switches its main view by `artifact_scope`; it never scans or aggregates unrelated reports.

- `package_source` reviews frames decoded from the actual encoded `sticker.webp`; authored source frames are comparison evidence.
- `render_track` reviews the exact ordered render PNG sequence and clearly labels it as a frame-track preview rather than an encoded deliverable.
- `export_files` reviews frames decoded from the actual exported GIF, its optional preview PNG, and the source track used for comparison.

The primary transport always controls the current report target. The semantic hold remains motion metadata but appears only as a timeline/frame marker and jump target. The 50×50 stress check shows both true display size and a 5× inspection zoom.

The generator validates report state, fingerprint, bindings, and the reference image before writing. Stale or missing evidence fails closed and leaves an existing Review Page unchanged. Regenerate immediately before sharing; Review HTML is not included in artifact fingerprints and cannot establish or preserve validation.

## Technical validation

Use the scripts to verify dimensions, file formats, frame count, durations, loop metadata, Alpha, paths, fingerprints, and platform constraints. A failed technical validation must not be overridden by visual judgment.

## Identity

- Compare every anchor and the contact sheet with the reference image.
- Judge the subject's signature silhouette against the approved reference, not in isolation.
- Confirm fixed marks, palette, material, face or functional anchors, and proportions remain recognizable.
- Treat automatic image metrics as candidate signals, not final identity judgments.

## Meaning and timing

- Confirm the animation communicates the requested meaning without its filename or an explanation.
- Confirm text is exact, readable, correctly ordered, and visible long enough.
- Confirm the primary semantic frame has the longest intentional hold.
- Confirm anticipation, action, hold, and recovery do not introduce an unrelated second meaning.
- Replay the loop several times and reject unintended jumps, flashes, or position resets.

## Alpha and composition

- Inspect edges over light, dark, and checkerboard backgrounds.
- Reject background remnants, work-color spill, bright halos, clipped details, and canvas-edge contact.
- Confirm every source frame uses the same RGBA canvas and subject baseline unless motion requires otherwise.
- Confirm shadows do not become opaque background patches.
- For salvaged local components, inspect the composited boundary on light and dark backgrounds and reject seams, duplicated features, leftover source pixels, or base-subject drift.
- For pressing, sitting, carrying, or contact actions, reject unintended air gaps and implausible deep intersections at the semantic hold. Judge contact against the local silhouettes, not only global bounding boxes.

## Small-size readability

- Inspect the semantic hold at 50x50 and at the target platform's smallest display size.
- Treat 50x50 as a stress test for the signature silhouette, main expression, and primary semantic signal; do not require long text to remain letter-perfect at that size.
- Require exact text to remain readable at the target platform's actual smallest display size. If that size is not yet known, record platform text readability as pending instead of using 50x50 as a substitute.
- Remove decorative signals that compete with the primary subject when reduced.

## Record visual validation

Run `scripts/record_visual_validation.py` against `validation/report.json`, an optional render-track report, and each export report:

- Set `visual_validation.status` to `pass` or `fail`.
- Add concise notes for identity, meaning, loop, Alpha, and small-size checks.
- Set `deliverable_ready` to true only when both `technical_validation` and `visual_validation` pass.
- Treat every repack as a new validation boundary. The candidate report resets visual validation to pending.
- Require the report fingerprint to still match the files being validated. Regenerate instead of passing a stale report after any artifact changes.
