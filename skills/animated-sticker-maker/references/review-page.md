# Review page

`scripts/generate_review.py` creates one offline, read-only HTML light table for one exact Validation Report. It uses one interface and automatically selects the main view from `artifact_scope`.

## Generate

When the package does not include its reference:

```bash
python <skill-dir>/scripts/generate_review.py \
  <validation-report.json> \
  --reference-image <original-reference-image>
```

When `source/reference.json` declares an `included_path`, omit `--reference-image`; the generator uses the bound package copy and rejects an external replacement.

The default output is `<report-stem>.review.html` beside the report. `--output <name.html>` may select another direct child of the same report directory. The file is written atomically.

## Exact boundary

One page represents one report and its bound files:

| `artifact_scope` | Main review target | Frame inspector |
| --- | --- | --- |
| `package_source` | Actual encoded `sticker.webp` | Authored keyframes |
| `render_track` | Ordered render PNG sequence with exact declared timing | The same render sequence |
| `export_files` | Actual exported GIF and optional preview PNG | The authored or render source track selected by the export |

The generator accepts internally consistent `pending`, `pass`, technical-fail, and visual-fail reports. It rejects missing files, stale fingerprints, inconsistent bindings, invalid report state, an absent external reference, and a reference SHA-256 mismatch. A render-track page also requires the package source report to remain valid because the reference identity evidence belongs to that source boundary.

## Interface

The Animation Inspection Light Table shows:

- the verified reference;
- the real review target on checker, light, and dark exposures;
- native encoded playback for GIF/WebP, without pretending the browser can pause or change its speed;
- a controllable source-frame inspector with play, pause, speed, scrubbing, and frame stepping;
- the semantic hold extracted from the actual encoded artifact, or mapped to the corresponding render frame;
- a 50×50 stress view;
- all authored keyframes;
- at most 24 evenly sampled render thumbnails while keeping every render frame accessible through the player;
- existing visual-validation notes;
- a collapsed technical section containing state, constraints, checks, provenance, paths, and hashes.

The page uses only embedded CSS and JavaScript. Media remains linked by contained relative paths, except for a verified external reference and extracted semantic frame, which are embedded in the HTML.

## Agent interaction

The page never writes validation. Share the freshly generated local file when user judgment is useful, collect feedback through the agent conversation, and use `record_visual_validation.py` as the only formal write path.

Regenerate before every share. If the visual result is recorded and the final status must be displayed, regenerate afterward. Do not archive the page as evidence, add it to an artifact fingerprint, or deliver it as part of the sticker package.
