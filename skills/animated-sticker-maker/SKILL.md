---
name: animated-sticker-maker
description: Make one transparent animated sticker package from one static reference image and one natural-language motion prompt. Use only when the user explicitly names or invokes animated-sticker-maker (for example, $animated-sticker-maker on hosts with dollar-sign invocation); do not trigger for ordinary image, GIF, animation, or multi-sticker pack requests.
license: Apache-2.0
---

# Animated Sticker Maker

Turn one reference image and one motion prompt into one short, transparent animated sticker. Derive the identity lock, motion plan, frame timing, validation plan, and export settings internally; do not make the user fill in routine production choices.

Resolve every script and reference path against the directory containing this `SKILL.md`.

## Inputs and boundaries

Require only:

1. `reference_image`: one static image containing a clear primary subject.
2. `prompt`: natural language describing the intended expression, action, text, loop, or target platform.

Support people, pets, mascots, illustrations, objects, and logos. If the image has multiple plausible subjects and the prompt does not identify one, ask once before generating. Do not promise stable multi-subject acting, scene animation, or camera motion.

Produce one sticker per invocation. For a multi-sticker series, keep shared identity specifications, pack ordering, release naming, and brand assets in the owning project, then invoke this Skill separately for each sticker. Do not turn project-specific pack orchestration into a generic Skill feature.

This is one [Agent Skills](https://agentskills.io/specification) package for hosts that support the standard; do not maintain a second host-specific instruction format. The host must provide a reference-conditioned raster generation or editing capability that can preserve the subject's identity. Use the host-native capability and fail before generation with a clear capability message when none is available. `agents/openai.yaml` is optional OpenAI UI and invocation metadata, not part of the workflow contract.

Use Python 3.10 or newer plus the packages in `requirements.txt` for deterministic processing. Do not make OpenCV a required dependency.

## Default output

Create this structure unless the prompt explicitly overrides it:

```text
output/<name>/
├── sticker.webp
├── source/
│   ├── frames/
│   │   ├── 000.png
│   │   └── ...
│   ├── rendered-frames/      # optional validated high-frame track
│   ├── reference.json        # basename, hash, and image metadata
│   └── motion.json
├── validation/
│   ├── contact-sheet.png
│   └── report.json
└── exports/                  # only when a platform or extra format is requested
    └── <platform>/
```

Use a workspace-local `output/<name>/` unless the user names another local destination. Derive `<name>` as a short, filesystem-safe slug from the subject and primary semantic beat. If it already exists, use `-2`, `-3`, and so on; do not overwrite an existing package by default. Honor an explicit release or public name when the user provides one.

Use `1024×1024` RGBA for continuous-tone, illustrated, or generated raster sources. For native pixel art or another strict low-resolution grid, preserve the logical source canvas and set `motion.resampling` to `nearest`; do not force it through a non-integer `1024×1024` redraw. Use 4–8 unique frames, per-frame durations, a total duration of about 1.2–2.0 seconds, and a 400–700 ms hold on the clearest semantic frame. Loop by default. Do not create `preview.gif` unless requested or required by the target platform.

## Workflow

### 1. Normalize the request

- Confirm that one reference image and one motion prompt are available. Extract the primary subject, one semantic beat, exact text, loop intent, and any named target platform.
- If the subject is ambiguous, ask once. If the reference image, prompt, or required host capability is missing, stop with a clear blocker before generating.
- If no platform is named, produce the platform-neutral package. A named platform is an optional export branch after the package passes validation.
- Select the output slug before creating files, using the collision rule above.

### 2. Lock identity and plan motion

Read [references/motion-plan.md](references/motion-plan.md). Inspect the reference at full size and small-icon size, classify recognizable features as fixed, flexible, or removable, and write `motion.json` before producing final frames.

Commit to one primary semantic beat, a small set of anchor poses, deterministic transitions, exact text layers, frame durations, and loop behavior. Generate only what cannot be obtained safely through deterministic transforms. Choose `motion.resampling` deliberately: `lanczos` for continuous-tone or illustrated raster work, and `nearest` for native pixel art or another strict logical grid.

Complete this stage only when the identity lock is explicit and each requested semantic element has a planned frame or deterministic layer.

### 3. Produce anchors and clean RGBA assets

Read the host's raster generation or editing instructions before generating. Always include the original reference when requesting a new anchor, ask for an isolated subject on transparency or a flat high-distance work color, and generate the fewest anchors needed.

Inspect every anchor immediately against the identity lock. Reject identity drift before building temporal frames. If a rejected full anchor contains a usable local expression or prop, salvage it only onto an approved identity-stable base; record the component source, extraction rule, and approved base in the motion plan. Never relabel a rejected full image as approved.

Preserve clean existing alpha. Otherwise read [references/transparency.md](references/transparency.md), choose a work color far from the subject palette, and run `scripts/chroma_key.py`. Keep shadows separate when the prompt or platform needs independent shadow control.

Complete this stage only when every full-frame anchor is usable, every salvaged component has a bounded deterministic role, and each asset has no opaque background, color spill, bright fringe, clipped protrusion, or canvas-edge contact.

### 4. Compose the authored animation

Create one RGBA PNG per unique authored frame. Preserve aspect ratio unless the requested motion calls for deformation. Render exact text in deterministic layers, and give every frame one purpose. Favor anticipation, action, one clear semantic hold, and a short recovery over evenly timed motion.

When a companion object presses, sits on, carries, or touches the subject, align it against the local silhouette beneath its footprint. Do not use the subject's global bounding-box edge as the contact plane when the surface is curved, notched, or deformed.

Complete this stage only when the sequence reads without filenames or explanation and the loop has no unintended jump, flash, or position reset.

### 5. Package and run technical validation

Run:

```bash
python <skill-dir>/scripts/package_sticker.py \
  --frames-dir <working-frames> \
  --motion <motion.json> \
  --reference-image <reference-image> \
  --output <output/name>
```

Pass `--expected-size <WIDTHxHEIGHT>` when the source canvas differs from `1024x1024`. Use `--include-reference` only when the user wants the original embedded; otherwise bind its basename, hash, dimensions, mode, format, and byte size without copying it. Use nonstandard timing or frame-count flags only when the prompt explicitly overrides the defaults. Do not continue to platform export when technical validation fails.

Read [references/validation.md](references/validation.md) for the report contract and deterministic checks. Keep the package transactional, treat packaged `source/motion.json` as the self-contained source of truth, preserve artifact fingerprints, and keep `technical_validation` separate from `visual_validation`.

If `motion.render` is present, treat its explicit ordered frames as an optional separately validated render track. Keep authored keyframes as the default; never create or select the render track silently. Read the motion and platform references for its timing, resource, and export rules.

Complete this stage only when the WebP, normalized sources, reference metadata, motion plan, contact sheet, primary technical report, and every applicable render-track report exist and all applicable technical checks pass.

Every successful repack creates a fresh report with visual validation pending. Re-run visual validation after every repack; never preserve a prior visual pass across changed artifacts.

### 6. Inspect, record, and optionally export

Read [references/validation.md](references/validation.md) and [references/review-page.md](references/review-page.md). Generate a fresh Review Page immediately before inspection or sharing:

```bash
python <skill-dir>/scripts/generate_review.py <validation-report.json> \
  --reference-image <original-reference-image> \
  --language <en|zh>
```

Omit `--reference-image` when the package contains its bound reference. Choose `zh` for a Chinese conversation and `en` otherwise. Inspect the actual encoded review target, semantic-hold marker, Alpha on checker/light/dark backgrounds, true-size and zoomed 50×50 views, and frame exposure sheet. Authored or render frames are comparison evidence; the decoded WebP/GIF controls the package or export page.

Record the result with `scripts/record_visual_validation.py`. The report must retain its exact artifact fingerprint, and `deliverable_ready` is true only when technical and visual validation both pass. If the final status must appear on a shared Review Page, regenerate the page after recording it. A Review Page is disposable derived HTML, not evidence or a deliverable.

If a platform is requested, read [references/platform-exports.md](references/platform-exports.md), verify the current official constraints, and export only beneath `exports/<platform>/` from the validated package. Use authored keyframes by default; select a declared render track explicitly only when it materially improves the requested output. Each requested export needs its own technical and visual validation.

Before delivery, run `scripts/doctor.py` on the exact package, render-track, and export reports that will be delivered. Doctor is read-only; `incomplete` is expected while an applicable visual validation is pending. Read [references/doctor.md](references/doctor.md) for target selection and JSON output.

## Decision and recovery rules

- Decide routine timing, position, scale, work-color threshold, compression, and output-slug details without interrupting the user.
- A technical or visual failure caused by a safe, reversible issue may receive one focused automatic correction pass using only those safe adjustments. Repackage, regenerate the Review Page, and re-inspect; every repack resets visual validation.
- If the correction still fails, or a fix would change identity, meaning, anchor generation, or an explicit public output, stop and ask the user. Never override a failed technical gate with visual judgment.
- If the user participates, share the fresh Review Page and collect feedback in the conversation. The user does not need to run Python or submit a form.

## Delivery handoff

Use the current conversation language and always report these fields:

- `status`: `ready`, `incomplete`, or `blocked`;
- package path and primary Validation Report path;
- render-track report path when one exists;
- Review Page path when one was generated;
- every requested export and its report path;
- Doctor result for each exact delivered report;
- unresolved caveats, pending visual checks, external-reference requirements, or platform-spec limitations.

Never call an artifact ready unless its exact report has `technical_validation`, `visual_validation`, and `deliverable_ready: true`, and Doctor reports `healthy` for the delivered boundary. Do not present Review HTML as a package artifact, validation evidence, or deliverable.

## Escalation rule

Ask the user only when a missing choice changes the intended subject, requested meaning, or irreversible public output. Ask once for an ambiguous primary subject; stop clearly when a required input or host capability is unavailable. Make safe project-level adjustments automatically within the bounded recovery rule above.
