# Review page

`scripts/generate_review.py` creates one offline, read-only HTML light table for one exact Validation Report. It uses one interface and automatically selects the main view from `artifact_scope`.

## Generate

When the package does not include its reference:

```bash
python <skill-dir>/scripts/generate_review.py \
  <validation-report.json> \
  --reference-image <original-reference-image> \
  --language <en|zh>
```

When `source/reference.json` declares an `included_path`, omit `--reference-image`; the generator uses the bound package copy and rejects an external replacement.

The agent selects the page language from the user's working language: pass `--language zh` for Chinese conversations and `--language en` for every other language. English is the CLI default. The program contains both complete interface dictionaries and does not infer language from the host locale.

The default output is `<report-stem>.review.html` beside the report. `--output <name.html>` may select another direct child of the same report directory. The file is written atomically.

## Exact boundary

One page represents one report and its bound files:

| `artifact_scope` | Main review target | Frame inspector |
| --- | --- | --- |
| `package_source` | Frames decoded from actual `sticker.webp` | The same decoded artifact frames |
| `render_track` | Ordered render PNG sequence with exact declared timing | The same render sequence |
| `export_files` | Frames decoded from the actual exported GIF | The same decoded artifact frames |

The generator accepts internally consistent `pending`, `pass`, technical-fail, and visual-fail reports. It rejects missing files, stale fingerprints, inconsistent bindings, invalid report state, an absent external reference, and a reference SHA-256 mismatch. A render-track page also requires the package source report to remain valid because the reference identity evidence belongs to that source boundary.

Package and export pages decode their encoded artifact into PNG evidence when the HTML is generated. Their authored or selected render track remains visible only as comparison evidence. Render pages use the pre-encode PNG track directly. The same transport therefore always controls the current report's primary review target.

## Interface

The Animation Inspection Light Table shows:

- the verified reference;
- the real review target on checker, light, and dark exposures;
- a controllable primary-target inspector with play, pause, speed, scrubbing, and frame stepping;
- a semantic-hold marker on the timeline and primary frame sheet, with a jump-to-hold control and an inline explanation of its meaning and source;
- a 50×50 stress view showing both true display size and a 5× inspection zoom;
- authored keyframes or the selected export source track as comparison evidence;
- at most 24 evenly sampled render thumbnails while keeping every render frame accessible through the player;
- existing visual-validation notes;
- a collapsed technical section containing state, constraints, checks, provenance, paths, and hashes.

The implementation keeps the HTML template, CSS, and JavaScript in separate Skill assets for maintainability, then embeds those interface assets into one offline HTML document. Source and render PNG media remains linked by contained relative paths. A verified external reference and decoded encoded-artifact frames are embedded in the HTML. The generated model and HTML use report-relative or package-relative display names and do not expose absolute host paths.

The semantic hold is an inspection anchor, not an automatic playback pause. When `motion.semantic_hold_frame` is declared, the marker uses the midpoint of that authored frame's time span and maps that timestamp onto the current review track. Without a declaration, it falls back to the midpoint of the longest authored frame. The page states which rule was used.

## Agent interaction

The page never writes validation. Share the freshly generated local file when user judgment is useful, collect feedback through the agent conversation, and use `record_visual_validation.py` as the only formal write path.

Regenerate before every share. If the visual result is recorded and the final status must be displayed, regenerate afterward. Do not archive the page as evidence, add it to an artifact fingerprint, or deliver it as part of the sticker package.
