from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import doctor, motion_plan, packaged_motion


class DoctorTests(unittest.TestCase):
    def test_motion_diagnosis_uses_versioned_json_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            motion_path = Path(temporary) / "motion.json"
            motion_path.write_text(
                json.dumps(
                    motion_plan(
                        [{"file": "frames/000.png", "duration_ms": 1200}]
                    )
                ),
                encoding="utf-8",
            )

            result = doctor.diagnose("motion", motion_path).result()

            self.assertEqual(result["schema_version"], 1)
            self.assertEqual(result["status"], "healthy")
            self.assertEqual(result["target"]["kind"], "motion")
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["warnings"], [])
            self.assertTrue(
                all("id" in check and "status" in check for check in result["checks"])
            )

    def test_motion_diagnosis_rejects_ambiguous_reference_variant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            motion_path = Path(temporary) / "motion.json"
            motion = motion_plan(
                [{"file": "frames/000.png", "duration_ms": 1200}]
            )
            motion["reference"] = {
                "filename": "reference.png",
                "sha256": "0" * 64,
                "included_path": None,
            }
            motion_path.write_text(json.dumps(motion), encoding="utf-8")

            result = doctor.diagnose("motion", motion_path).result()

            self.assertEqual(result["status"], "invalid")
            self.assertTrue(
                any(check["id"] == "motion.variant" for check in result["errors"])
            )

    def test_unscoped_diagnosis_rejects_ambiguous_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "motion.json").write_text("{}", encoding="utf-8")
            (root / "sticker.export-report.json").write_text(
                "{}",
                encoding="utf-8",
            )

            inferred = doctor.infer_target(root)

            self.assertIsNone(inferred)

    def test_packaged_motion_requires_canonical_track_paths(self) -> None:
        cases = {
            "authored": packaged_motion(
                [
                    {
                        "file": "rendered-frames/0000.png",
                        "duration_ms": 1200,
                    }
                ]
            ),
            "render": packaged_motion(
                [{"file": "frames/000.png", "duration_ms": 1200}],
                render={
                    "target_fps": 1,
                    "frames": [
                        {
                            "file": "frames/000.png",
                            "duration_ms": 1200,
                        }
                    ],
                },
            ),
        }
        for name, motion in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                motion_path = Path(temporary) / "motion.json"
                motion_path.write_text(json.dumps(motion), encoding="utf-8")

                result = doctor.diagnose("motion", motion_path).result()

                self.assertEqual(result["status"], "invalid")
                self.assertTrue(
                    any(check["id"] == "motion.schema" for check in result["errors"])
                )


if __name__ == "__main__":
    unittest.main()
