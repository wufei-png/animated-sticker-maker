#!/usr/bin/env python3
"""Doctor checks for one working or packaged motion plan."""

from __future__ import annotations

from pathlib import Path

from doctor_core import Diagnosis, load_json_object
from motion_schema import validate_motion


def motion_variant(motion: dict[str, object]) -> bool:
    """Return whether a motion plan is packaged; reject ambiguous variants."""
    has_working_reference = "reference_image" in motion
    has_packaged_reference = "reference" in motion
    if has_working_reference == has_packaged_reference:
        raise ValueError(
            "motion must contain exactly one of reference_image or reference"
        )
    return has_packaged_reference


def diagnose_motion(path: Path, kind: str = "motion") -> Diagnosis:
    diagnosis = Diagnosis(kind, path)
    motion = diagnosis.capture(
        "motion.json",
        lambda: load_json_object(path),
        "motion plan is readable JSON",
        path,
    )
    if motion is None:
        return diagnosis
    packaged = diagnosis.capture(
        "motion.variant",
        lambda: motion_variant(motion),
        "motion plan has one unambiguous variant",
        path,
    )
    if packaged is None:
        return diagnosis
    diagnosis.capture(
        "motion.schema",
        lambda: validate_motion(motion, packaged=packaged),
        f"motion schema v2 is valid ({'packaged' if packaged else 'working'})",
        path,
    )
    return diagnosis
