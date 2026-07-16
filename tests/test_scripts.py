from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from PIL import Image, features

from support import (
    artifact_integrity,
    export_platform_gif,
    make_frame,
    media_validation,
    motion_plan,
    motion_schema,
    package_sticker,
    packaged_motion,
    passing_package_checks,
    passing_render_checks,
    record_visual_validation,
)


class PackageStickerTests(unittest.TestCase):
    def test_frame_paths_cannot_escape_the_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            outside = root / "outside.png"
            make_frame(outside, (20, 80, 70, 255))
            with self.assertRaisesRegex(ValueError, "must stay beneath"):
                package_sticker.resolve_frame(frames_dir, "../outside.png")

    def test_package_normalizes_motion_paths_and_semantic_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "input"
            frames_dir.mkdir()
            names = ["rest.png", "tilt.png", "hold.png", "return.png"]
            colors = [
                (20, 80, 70, 255),
                (40, 100, 90, 255),
                (60, 120, 110, 255),
                (80, 140, 130, 255),
            ]
            for name, color in zip(names, colors):
                make_frame(frames_dir / name, color)

            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [
                            {"file": name, "duration_ms": 300}
                            for name in names
                        ],
                        semantic_hold_frame="hold.png",
                    )
                ),
                encoding="utf-8",
            )
            output = root / "package"
            stale_paths = [
                output / "source" / "rendered-frames" / "000.png",
                output / "validation" / "render-report.json",
                output / "exports" / "wechat" / "sticker.gif",
            ]
            for stale_path in stale_paths:
                stale_path.parent.mkdir(parents=True, exist_ok=True)
                stale_path.write_bytes(b"stale")
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=frames_dir / "rest.png",
                include_reference=False,
                output=output,
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )

            self.assertEqual(package_sticker.package(args), 0)
            packaged = json.loads(
                (output / "source" / "motion.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [entry["file"] for entry in packaged["frames"]],
                [f"frames/{index:03d}.png" for index in range(4)],
            )
            self.assertEqual(packaged["semantic_hold_frame"], "frames/002.png")
            self.assertEqual(packaged["schema_version"], 2)
            self.assertEqual(packaged["loop"], True)
            self.assertEqual(packaged["canvas"], [16, 16])
            self.assertEqual(packaged["resampling"], "lanczos")
            self.assertNotIn(str(frames_dir.resolve()), json.dumps(packaged))
            reference = json.loads(
                (output / "source" / "reference.json").read_text(encoding="utf-8")
            )
            self.assertEqual(reference["filename"], "rest.png")
            self.assertIsNone(reference["included_path"])
            self.assertFalse((output / "source" / "reference").exists())
            report = json.loads(
                (output / "validation" / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["technical_validation"]["status"], "pass")
            self.assertTrue(
                report["technical_validation"]["checks"]["sticker_transparency_preserved"]
            )
            self.assertTrue(report["webp_encoding"]["alpha_guard_applied"])
            self.assertEqual(
                report["artifact_fingerprint"],
                artifact_integrity.package_fingerprint(output),
            )
            with Image.open(output / "sticker.webp") as sticker:
                self.assertEqual(sticker.format, "WEBP")
                self.assertEqual(sticker.mode, "RGBA")
                self.assertEqual(sticker.n_frames, 4)
            for stale_path in stale_paths:
                self.assertFalse(stale_path.exists())
            _, preview_index = export_platform_gif.automatic_preview_frame(
                output, packaged, (16, 16)
            )
            self.assertEqual(preview_index, 2)
            for index, color in enumerate(colors):
                with Image.open(
                    output / "source" / "frames" / f"{index:03d}.png"
                ) as copied:
                    self.assertEqual(copied.getpixel((8, 8)), color)

    def test_reference_copy_is_opt_in_and_fingerprint_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            for index in range(4):
                make_frame(
                    frames_dir / f"{index}.png",
                    (20 + index * 30, 80 + index * 20, 70, 255),
                )
            reference = root / "master.png"
            make_frame(reference, (200, 100, 40, 255))
            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [
                            {"file": f"{index}.png", "duration_ms": 300}
                            for index in range(4)
                        ]
                    )
                ),
                encoding="utf-8",
            )
            output = root / "package"
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=reference,
                include_reference=True,
                output=output,
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )
            self.assertEqual(package_sticker.package(args), 0)
            included = output / "source" / "reference" / "master.png"
            self.assertEqual(included.read_bytes(), reference.read_bytes())
            report = json.loads(
                (output / "validation" / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                report["artifact_fingerprint"],
                artifact_integrity.package_fingerprint(output),
            )
            make_frame(included, (220, 20, 20, 255))
            self.assertNotEqual(
                report["artifact_fingerprint"],
                artifact_integrity.package_fingerprint(output),
            )

    def test_render_track_is_ingested_from_motion_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            render_dir = root / "render"
            frames_dir.mkdir()
            render_dir.mkdir()
            for index in range(4):
                make_frame(
                    frames_dir / f"{index}.png",
                    (20 + index * 30, 80 + index * 20, 70, 255),
                )
            for index in range(6):
                make_frame(
                    render_dir / f"{index}.png",
                    (20 + index, 80 + index, 70, 255),
                )
            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [
                            {"file": f"{index}.png", "duration_ms": 300}
                            for index in range(4)
                        ],
                        resampling="nearest",
                        render={
                            "target_fps": 5,
                            "frames": [
                                {
                                    "file": f"render/{index}.png",
                                    "duration_ms": 200,
                                }
                                for index in range(6)
                            ],
                        },
                    )
                ),
                encoding="utf-8",
            )
            output = root / "package"
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=frames_dir / "0.png",
                include_reference=False,
                output=output,
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )
            self.assertEqual(package_sticker.package(args), 0)
            packaged = json.loads(
                (output / "source" / "motion.json").read_text(encoding="utf-8")
            )
            self.assertEqual(packaged["render"]["target_fps"], 5)
            self.assertEqual(set(packaged["render"]), {"target_fps", "frames"})
            self.assertEqual(
                [entry["file"] for entry in packaged["render"]["frames"]],
                [f"rendered-frames/{index:04d}.png" for index in range(6)],
            )
            self.assertEqual(
                len(list((output / "source" / "rendered-frames").glob("*.png"))),
                6,
            )
            render_report = json.loads(
                (output / "validation" / "render-report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(render_report["technical_validation"]["status"], "pass")
            self.assertEqual(
                render_report["artifact_fingerprint"],
                artifact_integrity.render_track_fingerprint(output),
            )

    def test_failed_candidate_preserves_previous_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            for index in range(4):
                make_frame(
                    frames_dir / f"{index}.png",
                    (20 + index * 30, 80 + index * 20, 70, 255),
                )
            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [
                            {"file": f"{index}.png", "duration_ms": 300}
                            for index in range(4)
                        ]
                    )
                ),
                encoding="utf-8",
            )
            output = root / "package"
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=frames_dir / "0.png",
                include_reference=False,
                output=output,
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )
            self.assertEqual(package_sticker.package(args), 0)
            original = (output / "sticker.webp").read_bytes()
            Image.new("RGB", (16, 16), (255, 255, 255)).save(frames_dir / "0.png")
            self.assertEqual(package_sticker.package(args), 2)
            self.assertEqual((output / "sticker.webp").read_bytes(), original)
            failed_report = json.loads(
                (root / "package.failed" / "validation" / "report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(failed_report["status"], "technical_validation_failed")

    def test_semantic_hold_must_be_an_authored_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            for index in range(4):
                make_frame(frames_dir / f"{index}.png", (20 + index, 80, 70, 255))
            make_frame(frames_dir / "orphan.png", (200, 40, 40, 255))
            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [
                            {"file": f"{index}.png", "duration_ms": 300}
                            for index in range(4)
                        ],
                        semantic_hold_frame="orphan.png",
                    )
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=frames_dir / "0.png",
                include_reference=False,
                output=root / "package",
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )
            with self.assertRaisesRegex(ValueError, "semantic_hold_frame must name"):
                package_sticker.package(args)

    def test_loop_must_be_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "motion.json"
            path.write_text(
                json.dumps(
                    motion_plan(
                        [{"file": "0.png", "duration_ms": 300}],
                        loop="false",
                    )
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "motion.loop must be a boolean"):
                package_sticker.load_motion(path)

    def test_schema_v2_requires_the_portable_workflow_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "motion.json"
            motion = motion_plan([{"file": "0.png", "duration_ms": 1200}])
            motion["schema_version"] = 1
            path.write_text(json.dumps(motion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema_version must be 2"):
                package_sticker.load_motion(path)

            motion["schema_version"] = 2
            motion.pop("identity_lock")
            path.write_text(json.dumps(motion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity_lock must be an object"):
                package_sticker.load_motion(path)

            motion = motion_plan([{"file": "0.png", "duration_ms": 1200}])
            motion["transparency"] = {"strategy": "existing-alpha"}
            path.write_text(json.dumps(motion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "work_color must be present"):
                package_sticker.load_motion(path)

    def test_artifact_fingerprint_rejects_old_packaged_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            frames_dir = package / "source" / "frames"
            frames_dir.mkdir(parents=True)
            make_frame(frames_dir / "000.png", (20, 80, 70, 255))
            motion = packaged_motion(
                [{"file": "frames/000.png", "duration_ms": 1200}]
            )
            motion["schema_version"] = 1
            (package / "source" / "motion.json").write_text(
                json.dumps(motion),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "schema_version must be 2"):
                artifact_integrity.package_fingerprint(package)

    def test_render_track_uses_declared_order_not_filename_sorting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            render_dir = root / "render"
            frames_dir.mkdir()
            render_dir.mkdir()
            for index in range(4):
                make_frame(
                    frames_dir / f"{index}.png",
                    (20 + index * 30, 80 + index * 20, 70, 255),
                )
            render_colors = {
                "1.png": (10, 0, 0, 255),
                "2.png": (20, 0, 0, 255),
                "10.png": (100, 0, 0, 255),
            }
            for name, color in render_colors.items():
                make_frame(render_dir / name, color)
            declared_names = ["1.png", "2.png", "10.png"]
            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [
                            {"file": f"{index}.png", "duration_ms": 300}
                            for index in range(4)
                        ],
                        render={
                            "target_fps": 2,
                            "frames": [
                                {
                                    "file": f"render/{name}",
                                    "duration_ms": 400,
                                }
                                for name in declared_names
                            ],
                        },
                    )
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=frames_dir / "0.png",
                include_reference=False,
                output=root / "package",
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )
            self.assertEqual(package_sticker.package(args), 0)
            actual = []
            for index in range(3):
                with Image.open(
                    args.output / "source" / "rendered-frames" / f"{index:04d}.png"
                ) as frame:
                    actual.append(frame.getpixel((8, 8)))
            self.assertEqual(actual, [render_colors[name] for name in declared_names])

    def test_render_track_rejects_inconsistent_fps_and_excessive_frame_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "motion.json"
            mismatched_duration = motion_plan(
                [{"file": "0.png", "duration_ms": 1200}],
                render={
                    "target_fps": 4,
                    "frames": [
                        {"file": f"render/{index}.png", "duration_ms": 250}
                        for index in range(4)
                    ],
                },
            )
            path.write_text(json.dumps(mismatched_duration), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "same total duration"):
                package_sticker.load_motion(path)

            motion = motion_plan(
                [{"file": "0.png", "duration_ms": 1200}],
                render={
                    "target_fps": 30,
                    "frames": [
                        {"file": f"render/{index}.png", "duration_ms": 300}
                        for index in range(4)
                    ],
                },
            )
            path.write_text(json.dumps(motion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "target_fps is inconsistent"):
                package_sticker.load_motion(path)

            motion["render"] = {
                "target_fps": 100,
                "frames": [
                    {"file": f"render/{index}.png", "duration_ms": 10}
                    for index in range(241)
                ],
            }
            path.write_text(json.dumps(motion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at most 240"):
                package_sticker.load_motion(path)

            self.assertEqual(
                motion_schema.validate_render_pixel_budget(64 * 1024 * 1024),
                64 * 1024 * 1024,
            )
            with self.assertRaisesRegex(ValueError, "64M aggregate"):
                motion_schema.validate_render_pixel_budget(65 * 1024 * 1024)

            motion = motion_plan(
                [{"file": "0.png", "duration_ms": 1200}],
                render={
                    "target_fps": 1,
                    "frames": [{"file": "render/0.png", "duration_ms": 1200}],
                    "frame_count": 1,
                },
            )
            path.write_text(json.dumps(motion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "removed schema v1 fields"):
                package_sticker.load_motion(path)

    def test_render_track_limits_actual_input_pixels_before_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            render_dir = root / "render"
            frames_dir.mkdir()
            render_dir.mkdir()
            for index in range(4):
                make_frame(frames_dir / f"{index}.png", (20 + index, 80, 70, 255))
            for index in range(2):
                make_frame(
                    render_dir / f"{index}.png",
                    (100 + index, 80, 70, 255),
                    size=20,
                )
            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [
                            {"file": f"{index}.png", "duration_ms": 300}
                            for index in range(4)
                        ],
                        render={
                            "target_fps": 2,
                            "frames": [
                                {
                                    "file": f"render/{index}.png",
                                    "duration_ms": 600,
                                }
                                for index in range(2)
                            ],
                        },
                    )
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=frames_dir / "0.png",
                include_reference=False,
                output=root / "package",
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )
            budget_globals = package_sticker.validate_render_pixel_budget.__globals__
            with mock.patch.dict(budget_globals, {"MAX_RENDER_PIXELS": 600}):
                with self.assertRaisesRegex(ValueError, "64M aggregate"):
                    package_sticker.package(args)

    @unittest.skipUnless(features.check("webp"), "Pillow has no WebP support")
    def test_packaged_png_is_real_png_even_when_input_is_webp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames_dir = root / "frames"
            frames_dir.mkdir()
            entries = []
            for index in range(4):
                path = frames_dir / f"{index}.webp"
                make_frame(path, (20 + index * 20, 80, 70, 255))
                entries.append({"file": path.name, "duration_ms": 300})
            motion_path = root / "motion.json"
            motion_path.write_text(
                json.dumps(motion_plan(entries)),
                encoding="utf-8",
            )
            output = root / "package"
            args = argparse.Namespace(
                frames_dir=frames_dir,
                motion=motion_path,
                reference_image=frames_dir / "0.webp",
                include_reference=False,
                output=output,
                expected_size=(16, 16),
                quality=92,
                allow_nonstandard_frame_count=False,
                allow_nonstandard_timing=False,
            )
            self.assertEqual(package_sticker.package(args), 0)
            report = json.loads(
                (output / "validation" / "report.json").read_text(encoding="utf-8")
            )
            self.assertTrue(
                report["technical_validation"]["checks"][
                    "sticker_durations_match_source"
                ]
            )
            with Image.open(output / "source" / "frames" / "000.png") as packaged:
                self.assertEqual(packaged.format, "PNG")
                self.assertEqual(packaged.mode, "RGBA")


class ExportPlatformGifTests(unittest.TestCase):
    def make_validated_package(self, root: Path) -> tuple[Path, Path]:
        package = root / "package"
        frames_dir = package / "source" / "frames"
        render_dir = package / "source" / "rendered-frames"
        validation_dir = package / "validation"
        frames_dir.mkdir(parents=True)
        render_dir.mkdir(parents=True)
        validation_dir.mkdir(parents=True)
        make_frame(frames_dir / "000.png", (20, 80, 70, 255))
        make_frame(frames_dir / "001.png", (80, 140, 130, 255))
        for index in range(4):
            make_frame(
                render_dir / f"{index:04d}.png",
                (20 + index * 20, 80 + index * 10, 70 + index * 10, 255),
            )
        (package / "source" / "motion.json").write_text(
            json.dumps(
                packaged_motion(
                    [
                        {"file": "frames/000.png", "duration_ms": 600},
                        {"file": "frames/001.png", "duration_ms": 600},
                    ],
                    render={
                        "target_fps": 4,
                        "frames": [
                            {
                                "file": f"rendered-frames/{index:04d}.png",
                                "duration_ms": 300,
                            }
                            for index in range(4)
                        ],
                    },
                )
            ),
            encoding="utf-8",
        )
        (validation_dir / "report.json").write_text(
            json.dumps(
                {
                    "status": "pass",
                    "artifact_scope": "package_source",
                    "artifact_fingerprint": artifact_integrity.package_fingerprint(package),
                    "technical_validation": {
                        "status": "pass",
                        "checks": passing_package_checks(render=True),
                    },
                    "visual_validation": {
                        "status": "pass",
                        "notes": {
                            "identity": "stable",
                            "meaning": "clear",
                            "loop": "clean",
                            "alpha": "clean",
                            "small_size": "readable",
                        },
                    },
                    "deliverable_ready": True,
                }
            ),
            encoding="utf-8",
        )
        track_report = validation_dir / "render-report.json"
        track_report.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "artifact_scope": "render_track",
                    "artifact_fingerprint": artifact_integrity.render_track_fingerprint(package),
                    "technical_validation": {
                        "status": "pass",
                        "checks": passing_render_checks(),
                    },
                    "visual_validation": {
                        "status": "pass",
                        "notes": {
                            "identity": "stable",
                            "meaning": "clear",
                            "loop": "clean",
                            "alpha": "clean",
                            "small_size": "readable",
                        },
                    },
                    "deliverable_ready": True,
                }
            ),
            encoding="utf-8",
        )
        return package, track_report

    def test_top_level_pass_without_technical_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, _ = self.make_validated_package(Path(temporary))
            (package / "validation" / "report.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "artifact_scope": "package_source",
                        "artifact_fingerprint": artifact_integrity.package_fingerprint(package),
                        "visual_validation": {"status": "pass"},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "technical_validation"):
                export_platform_gif.load_validated_package(
                    package, allow_unvalidated=False
                )

    def test_nested_pass_without_successful_checks_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, _ = self.make_validated_package(Path(temporary))
            report_path = package / "validation" / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["technical_validation"] = {"status": "pass", "checks": {}}
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checks must be a non-empty object"):
                export_platform_gif.load_validated_package(
                    package,
                    allow_unvalidated=False,
                )

    def test_placeholder_technical_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, _ = self.make_validated_package(Path(temporary))
            report_path = package / "validation" / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["technical_validation"]["checks"] = {"placeholder": True}
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "evidence contract"):
                export_platform_gif.load_validated_package(
                    package,
                    allow_unvalidated=False,
                )

    def test_render_track_requires_its_own_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, track_report = self.make_validated_package(Path(temporary))
            source_report_path = package / "validation" / "report.json"
            source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
            source_report.pop("technical_validation")
            source_report_path.write_text(json.dumps(source_report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "technical_validation"):
                export_platform_gif.load_validated_package(
                    package, allow_unvalidated=False, frame_track="render"
                )

            source_report["technical_validation"] = {
                "status": "pass",
                "checks": passing_package_checks(render=True),
            }
            source_report_path.write_text(json.dumps(source_report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires --track-report"):
                export_platform_gif.load_validated_package(
                    package, allow_unvalidated=False, frame_track="render"
                )

            frames, durations, _, source_validation, track_validation = (
                export_platform_gif.load_validated_package(
                    package,
                    allow_unvalidated=False,
                    frame_track="render",
                    track_report=track_report,
                )
            )
            self.assertEqual(len(frames), 4)
            self.assertEqual(durations, [300, 300, 300, 300])
            self.assertEqual(source_validation["aggregate"], "pass")
            self.assertEqual(source_validation["technical"], "pass")
            assert track_validation is not None
            self.assertEqual(track_validation["technical"], "pass")

    def test_render_track_mutation_after_validation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, track_report = self.make_validated_package(Path(temporary))
            make_frame(
                package / "source" / "rendered-frames" / "0000.png",
                (220, 30, 30, 255),
            )
            with self.assertRaisesRegex(ValueError, "validation artifacts changed"):
                export_platform_gif.load_validated_package(
                    package,
                    allow_unvalidated=False,
                    frame_track="render",
                    track_report=track_report,
                )

    def test_source_mutation_after_validation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, _ = self.make_validated_package(Path(temporary))
            make_frame(
                package / "source" / "frames" / "000.png",
                (220, 30, 30, 255),
            )
            with self.assertRaisesRegex(ValueError, "validation artifacts changed"):
                export_platform_gif.load_validated_package(
                    package,
                    allow_unvalidated=False,
                )

    def test_resample_timeline_preserves_duration_and_semantic_order(self) -> None:
        frames = [Image.new("RGBA", (2, 2), (value, 0, 0, 255)) for value in (1, 2, 3)]
        sampled, durations = export_platform_gif.resample_timeline(
            frames, [100, 300, 600], fps=5
        )
        self.assertEqual([frame.getpixel((0, 0))[0] for frame in sampled], [1, 2, 3, 3, 3])
        self.assertEqual(sum(durations), 1000)
        self.assertTrue(all(duration % 10 == 0 for duration in durations))

    def test_adaptive_export_lowers_fps_before_palette_floor(self) -> None:
        frames = [Image.new("RGBA", (2, 2), (index, 0, 0, 255)) for index in range(30)]
        durations = [40] * 30

        def fake_write(
            candidate_frames, candidate_durations, path, colors, alpha_threshold, loop
        ):
            del candidate_durations, alpha_threshold, loop
            path.write_bytes(b"x" * (len(candidate_frames) * colors * 10))

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "sticker.gif"
            with mock.patch.object(export_platform_gif, "write_gif", side_effect=fake_write):
                _, selected_durations, colors, byte_size, fps, attempts = (
                    export_platform_gif.export_gif(
                        frames,
                        durations,
                        output,
                        max_bytes=20_000,
                        alpha_threshold=96,
                        loop=True,
                        min_colors=64,
                        fps_candidates=(30, 20),
                    )
                )
            self.assertEqual((fps, colors), (20, 64))
            self.assertEqual(byte_size, 15_360)
            self.assertEqual(sum(selected_durations), 1200)
            self.assertTrue(all(attempt["colors"] >= 64 for attempt in attempts))

    def test_palette_sampling_is_bounded_before_concatenation(self) -> None:
        frames = [
            Image.new("RGBA", (64, 64), (index, 80, 70, 255))
            for index in range(48)
        ]
        samples = export_platform_gif.collect_palette_samples(
            frames,
            alpha_threshold=96,
            max_samples=500,
        )
        self.assertLessEqual(len(samples), 500)
        self.assertGreater(len(samples), 0)

    def test_fps_candidates_must_be_unique_and_descending(self) -> None:
        self.assertEqual(export_platform_gif.parse_fps_candidates("30,24,15"), (30, 24, 15))
        with self.assertRaises(argparse.ArgumentTypeError):
            export_platform_gif.parse_fps_candidates("24,30")
        with self.assertRaises(argparse.ArgumentTypeError):
            export_platform_gif.parse_fps_candidates("30,30")

    def test_nearest_resampling_upscales_native_pixel_art_without_new_colors(self) -> None:
        frame = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
        frame.putdata(
            [
                (255, 0, 0, 255),
                (0, 255, 0, 255),
                (0, 0, 255, 255),
                (0, 0, 0, 0),
            ]
        )
        fitted = export_platform_gif.fit_frame(frame, (10, 10), "nearest")
        self.assertEqual(fitted.size, (10, 10))
        fitted_colors = {
            color for _, color in fitted.getcolors(maxcolors=fitted.width * fitted.height)
        }
        source_colors = {
            color for _, color in frame.getcolors(maxcolors=frame.width * frame.height)
        }
        self.assertEqual(
            fitted_colors,
            source_colors,
        )
        alpha_values = {
            value
            for _, value in fitted.getchannel("A").getcolors(
                maxcolors=fitted.width * fitted.height
            )
        }
        self.assertTrue(alpha_values.issubset({0, 255}))

    def test_nearest_resampling_uses_integer_scale_and_transparent_padding(self) -> None:
        frame = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        for y in (1, 2):
            for x in (1, 2):
                frame.putpixel((x, y), (255, 0, 0, 255))
        fitted = export_platform_gif.fit_frame(frame, (11, 11), "nearest")
        self.assertEqual(fitted.getchannel("A").getbbox(), (3, 3, 7, 7))
        top_row = fitted.getchannel("A").crop((0, 0, 11, 1))
        self.assertEqual(top_row.getextrema(), (0, 0))

    def test_platform_provenance_parsers_reject_invalid_values(self) -> None:
        self.assertEqual(
            export_platform_gif.parse_spec_url("https://example.com/spec"),
            "https://example.com/spec",
        )
        with self.assertRaises(argparse.ArgumentTypeError):
            export_platform_gif.parse_spec_url("file:///tmp/spec.html")
        self.assertEqual(
            export_platform_gif.parse_verified_on(date.today().isoformat()),
            date.today().isoformat(),
        )
        with self.assertRaises(argparse.ArgumentTypeError):
            export_platform_gif.parse_verified_on(
                (date.today() + timedelta(days=1)).isoformat()
            )

    def test_unvalidated_diagnostic_cannot_be_deliverable(self) -> None:
        complete = {
            "aggregate": "pass",
            "technical": "pass",
            "visual": "pass",
            "deliverable_ready": True,
        }
        incomplete = {
            "aggregate": "pending_visual_validation",
            "technical": "pass",
            "visual": "pending",
            "deliverable_ready": False,
        }
        self.assertEqual(
            export_platform_gif.export_validation_status(complete, None),
            ("pending_visual_validation", True),
        )
        self.assertEqual(
            export_platform_gif.export_validation_status(incomplete, None),
            ("diagnostic_unvalidated", False),
        )
        self.assertEqual(
            export_platform_gif.export_validation_status(
                complete,
                None,
                track_required=True,
            ),
            ("diagnostic_unvalidated", False),
        )

    def test_platform_name_and_output_paths_cannot_escape(self) -> None:
        self.assertEqual(export_platform_gif.parse_platform("wechat-v1"), "wechat-v1")
        with self.assertRaises(argparse.ArgumentTypeError):
            export_platform_gif.parse_platform("../../outside")
        with tempfile.TemporaryDirectory() as temporary:
            export_dir = Path(temporary) / "exports" / "wechat"
            export_dir.mkdir(parents=True)
            self.assertEqual(
                export_platform_gif.direct_export_path(
                    export_dir,
                    Path("custom.gif"),
                    "sticker.gif",
                    "--output",
                ),
                export_dir / "custom.gif",
            )
            with self.assertRaisesRegex(ValueError, "direct child"):
                export_platform_gif.direct_export_path(
                    export_dir,
                    Path(temporary) / "outside.gif",
                    "sticker.gif",
                    "--output",
                )

    def test_export_commit_restores_previous_files_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            staging.mkdir()
            old_gif = root / "sticker.gif"
            old_report = root / "report.json"
            old_gif.write_bytes(b"old-gif")
            old_report.write_bytes(b"old-report")
            new_gif = staging / "sticker.gif"
            missing_report = staging / "missing.json"
            new_gif.write_bytes(b"new-gif")
            with self.assertRaises(FileNotFoundError):
                export_platform_gif.commit_staged_files(
                    [
                        (new_gif, old_gif),
                        (missing_report, old_report),
                    ],
                    staging,
                )
            self.assertEqual(old_gif.read_bytes(), b"old-gif")
            self.assertEqual(old_report.read_bytes(), b"old-report")

    def test_export_report_requires_visual_validation_of_exact_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, _ = self.make_validated_package(Path(temporary))
            argv = [
                "export_platform_gif.py",
                "--package",
                str(package),
                "--platform",
                "test-platform",
                "--size",
                "16x16",
                "--spec-url",
                "https://example.com/official-spec",
                "--verified-on",
                date.today().isoformat(),
            ]
            with mock.patch.object(sys, "argv", argv):
                export_platform_gif.main()
            report_path = (
                package
                / "exports"
                / "test-platform"
                / "sticker.export-report.json"
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pending_visual_validation")
            self.assertFalse(report["deliverable_ready"])
            self.assertEqual(
                report["source_validation_report"]["artifact_fingerprint"],
                artifact_integrity.package_fingerprint(package),
            )
            self.assertEqual(
                report["source_validation_report"]["sha256"],
                artifact_integrity.sha256_path(package / "validation" / "report.json"),
            )
            record_visual_validation.update_report(
                argparse.Namespace(
                    report=report_path,
                    status="pass",
                    identity="stable",
                    meaning="clear",
                    loop="clean",
                    alpha="clean",
                    small_size="readable",
                )
            )
            validated = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(validated["status"], "pass")
            self.assertTrue(validated["deliverable_ready"])

    def test_non_looping_gif_omits_loop_extension(self) -> None:
        frames = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "once.gif"
            export_platform_gif.write_gif(
                frames,
                [100, 100],
                path,
                32,
                96,
                False,
            )
            with Image.open(path) as image:
                self.assertNotIn("loop", image.info)

    def test_runtime_supports_animated_webp(self) -> None:
        self.assertTrue(features.check("webp"))
        frames = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 128)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 128)),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "animated.webp"
            frames[0].save(
                path,
                save_all=True,
                append_images=frames[1:],
                duration=[123, 456],
                loop=0,
                lossless=True,
            )
            with Image.open(path) as image:
                self.assertEqual(image.format, "WEBP")
                self.assertEqual(image.n_frames, 2)
            self.assertEqual(
                package_sticker.webp_animation_durations(path),
                [123, 456],
            )

    def test_shared_gif_validation_rejects_non_gif_media(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "renamed.gif"
            frames = []
            for color in ((30, 90, 80, 255), (80, 140, 130, 255)):
                frame = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
                for y in range(2, 14):
                    for x in range(2, 14):
                        frame.putpixel((x, y), color)
                frames.append(frame)
            frames[0].save(
                path,
                format="WEBP",
                save_all=True,
                append_images=frames[1:],
                duration=[100, 100],
                loop=0,
                lossless=True,
            )

            with self.assertRaisesRegex(ValueError, "'gif_is_gif': False"):
                media_validation.validate_gif(
                    path,
                    (16, 16),
                    2,
                    [100, 100],
                    True,
                )


if __name__ == "__main__":
    unittest.main()
