# Motion plan

Write `motion.json` before packaging. Use this minimum shape:

```json
{
  "schema_version": 2,
  "id": "short-sticker-id",
  "prompt": "Original natural-language request",
  "reference_image": "path/to/reference.png",
  "canvas": [1024, 1024],
  "resampling": "lanczos",
  "loop": true,
  "identity_lock": {
    "subject": "Primary subject",
    "fixed": ["signature silhouette", "palette", "fixed marks"],
    "flexible": ["eyes", "pose", "temporary effects"],
    "forbidden": ["identity drift", "unrequested anatomy or props"]
  },
  "generation_plan": {
    "anchors": ["neutral", "new organic pose"],
    "deterministic": ["text", "translation", "opacity", "timing"]
  },
  "transparency": {
    "strategy": "existing-alpha",
    "work_color": null
  },
  "frames": [
    {
      "file": "frames/000.png",
      "duration_ms": 200,
      "description": "Neutral anticipation"
    },
    {
      "file": "frames/001.png",
      "duration_ms": 200,
      "description": "Primary action"
    },
    {
      "file": "frames/002.png",
      "duration_ms": 600,
      "description": "Clearest semantic hold"
    },
    {
      "file": "frames/003.png",
      "duration_ms": 200,
      "description": "Recovery into the loop"
    }
  ],
  "semantic_hold_frame": "frames/002.png"
}
```

When deterministic interpolation or compositing adds visible value, add this optional sibling of `frames` to the working motion plan:

```json
"render": {
  "target_fps": 5,
  "frames": [
    {"file": "working-render-frames/000.png", "duration_ms": 200},
    {"file": "working-render-frames/001.png", "duration_ms": 200},
    {"file": "working-render-frames/002.png", "duration_ms": 200},
    {"file": "working-render-frames/003.png", "duration_ms": 200},
    {"file": "working-render-frames/004.png", "duration_ms": 200},
    {"file": "working-render-frames/005.png", "duration_ms": 200}
  ]
}
```

`target_fps` is the user-facing numeric render target. `frames` is the authoritative temporal order; each entry binds one motion-relative PNG path to its duration. Packaging follows that array instead of inferring order from filenames, then normalizes the files to `source/rendered-frames/0000.png` and so on. Frame count and total duration are derived rather than duplicated in the motion plan. The render track must have the same total duration as the authored keyframes, and its declared frame density must agree with `target_fps` within one frame. A render track may contain at most 240 frames and 64M aggregate input pixels. It is optional derived evidence, not a replacement for the 4–8 authored semantic keyframes.

Planning rules:

- Use `schema_version: 2`; older schema versions are rejected. Include the complete minimum shape above: identity, generation, transparency, and per-frame descriptions are required workflow evidence, not optional annotations. Keep `loop` boolean, `canvas` as two positive integers, every frame path relative, and every `duration_ms` a positive integer; packaging rejects ambiguous coercions such as `"loop": "false"`.
- Commit to one primary semantic beat. Treat secondary effects as support.
- Use 4–8 unique frames by default; do not duplicate identical frames to simulate a hold. Increase `duration_ms` instead.
- Reserve 400–700 ms for the frame that communicates the meaning most clearly.
- Generate only anchors that cannot be obtained safely through deterministic transforms.
- If a rejected full anchor contributes a usable local component, record it explicitly as a component source together with the approved base anchor and deterministic extraction rule. Do not list the rejected image as an approved full anchor.
- Render exact text outside the image generator unless organic text deformation is itself the requested effect.
- Default to a loop. Plan the final recovery frame against the first frame rather than treating it as an afterthought.
- Keep companion objects visually subordinate unless the prompt explicitly makes them co-subjects.
- For physical contact, place a companion against the subject's local surface under its footprint; a global alpha bounding box is not a reliable contact plane for curved, notched, or deformed subjects.
- Keep a high-frame render track only when interpolation or deterministic compositing adds visible value. Validate its timing and visual result separately from the authored keyframes.
- Use `lanczos` resampling for continuous-tone or illustrated raster work. Use `nearest` for native pixel art and other strict logical grids, and keep their source canvas at the native grid or an intentional integer multiple instead of forcing `1024×1024`.
- If `semantic_hold_frame` is present, it must name exactly one entry in `frames`; do not point it at an unlisted still or a render-track frame.
