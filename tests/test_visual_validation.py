from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from support import (
    artifact_integrity,
    make_frame,
    packaged_motion,
    passing_export_checks,
    passing_package_checks,
    record_visual_validation,
)


class RecordVisualValidationTests(unittest.TestCase):
    def make_report(self, root: Path, source_validation_complete: bool = True) -> Path:
        package = root / "package"
        frames_dir = package / "source" / "frames"
        validation_dir = package / "validation"
        export_dir = package / "exports" / "test-platform"
        frames_dir.mkdir(parents=True, exist_ok=True)
        validation_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)
        make_frame(frames_dir / "000.png", (20, 80, 70, 255))
        make_frame(frames_dir / "001.png", (80, 140, 130, 255))
        (package / "source" / "motion.json").write_text(
            json.dumps(
                packaged_motion(
                    [
                        {"file": "frames/000.png", "duration_ms": 600},
                        {"file": "frames/001.png", "duration_ms": 600},
                    ]
                )
            ),
            encoding="utf-8",
        )
        source_fingerprint = artifact_integrity.package_fingerprint(package)
        source_report_path = validation_dir / "report.json"
        source_snapshot = {
            "aggregate": (
                "pass" if source_validation_complete else "pending_visual_validation"
            ),
            "technical": "pass",
            "visual": "pass" if source_validation_complete else "pending",
            "deliverable_ready": source_validation_complete,
        }
        source_visual: dict[str, object] = {
            "status": "pass" if source_validation_complete else "pending"
        }
        if source_validation_complete:
            source_visual["notes"] = {
                "identity": "stable",
                "meaning": "clear",
                "loop": "clean",
                "alpha": "clean",
                "small_size": "readable",
            }
        source_report_path.write_text(
            json.dumps(
                {
                    "status": source_snapshot["aggregate"],
                    "deliverable_ready": source_validation_complete,
                    "artifact_scope": "package_source",
                    "artifact_fingerprint": source_fingerprint,
                    "technical_validation": {
                        "status": "pass",
                        "checks": passing_package_checks(),
                    },
                    "visual_validation": source_visual,
                }
            ),
            encoding="utf-8",
        )
        artifact = export_dir / "sticker.gif"
        artifact.write_bytes(b"gif")
        report_path = export_dir / "sticker.export-report.json"
        fingerprint = artifact_integrity.fingerprint_files(
            [("artifact:sticker.gif", artifact)]
        )
        report_path.write_text(
            json.dumps(
                {
                    "status": (
                        "pending_visual_validation"
                        if source_validation_complete
                        else "diagnostic_unvalidated"
                    ),
                    "source_validation_complete": source_validation_complete,
                    "deliverable_ready": False,
                    "artifact_scope": "export_files",
                    "artifact_fingerprint": fingerprint,
                    "validation_artifacts": [
                        {
                            "path": "sticker.gif",
                            "sha256": artifact_integrity.sha256_path(artifact),
                        }
                    ],
                    "gif": {
                        "path": "sticker.gif",
                        "bytes": artifact.stat().st_size,
                        "max_bytes": None,
                        "sha256": artifact_integrity.sha256_path(artifact),
                        "validation": {"checks": passing_export_checks()},
                    },
                    "preview": None,
                    "technical_validation": {
                        "status": "pass",
                        "checks": passing_export_checks(),
                    },
                    "visual_validation": {"status": "pending"},
                    "platform": "test-platform",
                    "verified_on": "1990-07-31",
                    "spec_url": "https://www.w3.org/Graphics/GIF/spec-gif89a.txt",
                    "source_package": "../..",
                    "source_validation": source_snapshot,
                    "source_validation_report": {
                        "path": "../../validation/report.json",
                        "sha256": artifact_integrity.sha256_path(source_report_path),
                        "artifact_fingerprint": source_fingerprint,
                    },
                    "frame_track": "keyframes",
                    "resampling": "lanczos",
                }
            ),
            encoding="utf-8",
        )
        return report_path

    def validation_args(self, report: Path, **overrides: object) -> argparse.Namespace:
        values = {
            "report": report,
            "status": "pass",
            "identity": "stable",
            "meaning": "clear",
            "loop": "clean",
            "alpha": "clean",
            "small_size": "readable",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_validation_pass_is_bound_to_unchanged_export_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            record_visual_validation.update_report(self.validation_args(report_path))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["deliverable_ready"])

    def test_validation_rejects_changed_export_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            (report_path.parent / "sticker.gif").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "artifacts changed"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_incorrect_declared_artifact_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["validation_artifacts"][0]["sha256"] = "0" * 64
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sha256 does not match"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_requires_exact_export_artifact_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["gif"]["path"] = "unbound.gif"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must exactly match"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_placeholder_technical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["technical_validation"]["checks"] = {"placeholder": True}
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "evidence contract"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_invalid_export_provenance_and_limits(self) -> None:
        cases = {
            "missing-spec": (
                lambda report: report.pop("spec_url"),
                "spec_url",
            ),
            "future-verification": (
                lambda report: report.__setitem__("verified_on", "2999-01-01"),
                "cannot be in the future",
            ),
            "wrong-resampling": (
                lambda report: report.__setitem__("resampling", "nearest"),
                "resampling must match",
            ),
            "gif-over-limit": (
                lambda report: report["gif"].__setitem__("max_bytes", 1),
                "exceeds gif.max_bytes",
            ),
            "gif-low-bytes": (
                lambda report: report["gif"].__setitem__("bytes", 1),
                "gif.bytes does not match",
            ),
            "gif-wrong-sha": (
                lambda report: report["gif"].__setitem__("sha256", "0" * 64),
                "gif.sha256 does not match",
            ),
        }
        for name, (mutate, error) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                report_path = self.make_report(Path(temporary))
                report = json.loads(report_path.read_text(encoding="utf-8"))
                mutate(report)
                report_path.write_text(json.dumps(report), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, error):
                    record_visual_validation.update_report(
                        self.validation_args(report_path)
                    )

    def test_validation_binds_preview_metadata_to_its_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            preview = report_path.parent / "preview.png"
            preview.write_bytes(b"preview")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["validation_artifacts"].append(
                {
                    "path": preview.name,
                    "sha256": artifact_integrity.sha256_path(preview),
                }
            )
            report["artifact_fingerprint"] = artifact_integrity.fingerprint_files(
                [
                    ("artifact:sticker.gif", report_path.parent / "sticker.gif"),
                    ("artifact:preview.png", preview),
                ]
            )
            report["preview"] = {
                "path": preview.name,
                "bytes": preview.stat().st_size - 1,
                "max_bytes": None,
                "sha256": artifact_integrity.sha256_path(preview),
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "preview.bytes does not match"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_changed_source_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            source_report_path = (
                report_path.parent.parent.parent / "validation" / "report.json"
            )
            source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
            source_report["comment"] = "changed after export"
            source_report_path.write_text(json.dumps(source_report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source validation report changed"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_validation_rejects_invalid_or_contradictory_frame_track(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["frame_track"] = "other"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frame_track must be"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

            report_path = self.make_report(Path(temporary))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["track_validation"] = {"deliverable_ready": True}
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not declare"):
                record_visual_validation.update_report(
                    self.validation_args(report_path)
                )

    def test_empty_notes_and_unvalidated_source_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = self.make_report(root)
            with self.assertRaisesRegex(ValueError, "notes must be non-empty"):
                record_visual_validation.update_report(
                    self.validation_args(report_path, alpha="   ")
                )
            diagnostic = self.make_report(root, source_validation_complete=False)
            with self.assertRaisesRegex(ValueError, "cannot become deliverable"):
                record_visual_validation.update_report(
                    self.validation_args(diagnostic)
                )


if __name__ == "__main__":
    unittest.main()
