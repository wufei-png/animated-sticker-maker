# Doctor

`scripts/doctor.py` is the single read-only diagnosis entry point. It never repairs files, rewrites reports, scans arbitrary directory trees, or replaces maker-side visual inspection.

## Targets

Use an explicit target for automation:

```bash
python <skill-dir>/scripts/doctor.py motion <motion.json>
python <skill-dir>/scripts/doctor.py package <package-dir>
python <skill-dir>/scripts/doctor.py report <validation-report.json>
python <skill-dir>/scripts/doctor.py export <export-report.json>
```

Running without a target diagnoses the current directory only when it matches exactly one boundary:

- a package containing `source/motion.json` and `validation/report.json`;
- a directory containing one direct `motion.json`;
- a directory containing exactly one direct `*.export-report.json`;
- a directory containing exactly one direct `report.json` or `render-report.json`.

Ambiguous or unrecognized directories are `invalid`. Package diagnosis includes its primary source artifact and every render track declared by its motion plan. Platform exports remain separate boundaries and are never recursively scanned from a package.

## Results

| Status | Exit code | Meaning |
| --- | ---: | --- |
| `healthy` | `0` | All applicable deterministic checks and validation gates pass. |
| `invalid` | `1` | Schema, media, path, binding, technical validation, or an explicit visual result failed. |
| `incomplete` | `2` | Structure and technical checks pass, but an applicable visual validation is pending. |

Doctor re-opens packaged PNG, WebP, GIF, and preview media and checks their observable dimensions, frame count, timing, loop, Alpha, paths, hashes, report evidence, and upstream bindings. Motion diagnosis is schema-only; packaging remains responsible for validating working frame and reference files.

Doctor accepts only the current motion and Validation Report schemas. An older or unversioned report is `invalid` and must be regenerated; Doctor does not migrate artifacts.

## JSON

Pass `--json` before the target:

```bash
python <skill-dir>/scripts/doctor.py --json package <package-dir>
```

The stable public envelope begins with `schema_version: 1` and contains:

- `status`;
- `target` with `kind` and absolute `path`;
- ordered `checks` with stable IDs and `pass`, `warning`, or `error` status;
- filtered `errors`;
- filtered `warnings`.

Human-readable output is the default. JSON mode changes presentation only; status and exit codes stay the same.
