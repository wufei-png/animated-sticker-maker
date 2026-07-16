# Animated Sticker Validation

This context defines the portable artifacts and validation language used by the animated-sticker workflow.

## Language

**Motion Plan**:
The schema-versioned description of authored frames, timing, identity constraints, generation intent, transparency, and an optional ordered render track.
_Avoid_: Animation config, frame manifest

**Package**:
A platform-neutral animated sticker artifact containing normalized sources, the WebP deliverable, primary validation evidence, and validation evidence for every declared render track. Package health aggregates all of these declared components.
_Avoid_: Build directory, output folder

**Validation Report**:
A schema-versioned, fingerprint-bound record of technical facts, explicit policy overrides, and visual validation for one exact package, render track, or export.
_Avoid_: Approval, review result

**Artifact Boundary**:
One self-contained validation target: a working Motion Plan, Package, Validation Report, or platform Export.
_Avoid_: Workspace scan, project tree

**Doctor**:
The read-only deterministic command that diagnoses one Artifact Boundary and reports whether it is healthy, incomplete, or invalid.
_Avoid_: Validator, fixer

**Scoped Diagnosis**:
A Doctor invocation that explicitly selects a Motion Plan, Package, Validation Report, or Export instead of diagnosing the current directory.
_Avoid_: Partial doctor, auto scan

**Review Page**:
An instantaneous, read-only HTML view generated for one exact Validation Report and its bound files. It supports visual inspection but is neither validation evidence nor a deliverable.
_Avoid_: Approval page, review bundle

**Golden Workflow Fixture**:
A small synthetic sticker source exercised through two independent workflow scenarios: the default authored-keyframe export and the explicit render-track export. Both scenarios verify artifact structure, state transitions, bindings, and track-specific invalidation behavior from the same input.
_Avoid_: Golden binary, snapshot package

**Canned Visual Notes**:
Fixed test-only observations used to exercise visual-validation recording without claiming that software performed visual judgment.
_Avoid_: Automatic visual validation, synthetic approval
