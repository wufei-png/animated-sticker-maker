from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "skills" / "animated-sticker-maker" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from artifact_integrity import (  # noqa: E402
    package_fingerprint,
    report_artifact_fingerprint,
    render_track_fingerprint,
    sha256_path,
)
from media_validation import alpha_metrics  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "golden_workflow"
PACKAGE_SCRIPT = SCRIPTS / "package_sticker.py"
VALIDATION_SCRIPT = SCRIPTS / "record_visual_validation.py"
EXPORT_SCRIPT = SCRIPTS / "export_platform_gif.py"
DOCTOR_SCRIPT = SCRIPTS / "doctor.py"
SPEC_URL = "https://www.w3.org/Graphics/GIF/spec-gif89a.txt"
VERIFIED_ON = "1990-07-31"
NOTES = {
    "identity": "Synthetic tile remains recognizable.",
    "meaning": "Forward lean and hold remain clear.",
    "loop": "Return connects cleanly to the first frame.",
    "alpha": "Transparent border remains clean.",
    "small-size": "Primary tile and eye remain readable.",
}


class GoldenWorkflowTests(unittest.TestCase):
    def run_cli(
        self,
        script: Path,
        *arguments: object,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *(str(value) for value in arguments)],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def require_success(
        self,
        script: Path,
        *arguments: object,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = self.run_cli(script, *arguments, cwd=cwd)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def doctor(
        self,
        expected_status: str,
        kind: str | None = None,
        path: Path | None = None,
        *,
        cwd: Path | None = None,
    ) -> dict[str, object]:
        arguments: list[object] = ["--json"]
        if kind is not None:
            assert path is not None
            arguments.extend([kind, path])
        result = self.run_cli(DOCTOR_SCRIPT, *arguments, cwd=cwd)
        expected_code = {"healthy": 0, "invalid": 1, "incomplete": 2}[
            expected_status
        ]
        self.assertEqual(
            result.returncode,
            expected_code,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], expected_status)
        return payload

    def record_visual_validation(self, report: Path) -> None:
        arguments: list[object] = [report, "--status", "pass"]
        for name, note in NOTES.items():
            arguments.extend([f"--{name.replace('_', '-')}", note])
        self.require_success(VALIDATION_SCRIPT, *arguments)

    def package_fixture(self, root: Path) -> Path:
        package = root / "package"
        self.require_success(
            PACKAGE_SCRIPT,
            "--frames-dir",
            FIXTURE / "frames",
            "--motion",
            FIXTURE / "motion.json",
            "--reference-image",
            FIXTURE / "reference.png",
            "--output",
            package,
            "--expected-size",
            "16x16",
        )
        self.doctor("incomplete", "package", package)
        return package

    def export_fixture(
        self,
        package: Path,
        track: str,
        *,
        platform: str = "gif89a-fixture",
    ) -> Path:
        arguments: list[object] = [
            "--package",
            package,
            "--platform",
            platform,
            "--size",
            "32x32",
            "--max-bytes",
            "100000",
            "--preview-output",
            "preview.png",
            "--preview-max-bytes",
            "100000",
            "--spec-url",
            SPEC_URL,
            "--verified-on",
            VERIFIED_ON,
        ]
        if track == "render":
            arguments.extend(
                [
                    "--frame-track",
                    "render",
                    "--track-report",
                    package / "validation" / "render-report.json",
                    "--fps-candidates",
                    "5",
                    "--min-colors",
                    "32",
                ]
            )
        self.require_success(EXPORT_SCRIPT, *arguments)
        return (
            package
            / "exports"
            / platform
            / "sticker.export-report.json"
        )

    def build_passed_scenario(self, root: Path, track: str) -> tuple[Path, Path]:
        package = self.package_fixture(root)
        self.record_visual_validation(package / "validation" / "report.json")
        if track == "render":
            self.record_visual_validation(
                package / "validation" / "render-report.json"
            )
            self.doctor("healthy", "package", package)
        else:
            # The package as a whole remains incomplete because its optional
            # render track has not been visually validated. Keyframe export is
            # still valid because it does not consume that track.
            self.doctor("incomplete", "package", package)
        export_report = self.export_fixture(package, track)
        self.doctor("incomplete", "export", export_report)
        self.record_visual_validation(export_report)
        self.doctor("healthy", "export", export_report)
        self.doctor("healthy", "report", export_report)
        return package, export_report

    def mutate_png(self, path: Path) -> None:
        with Image.open(path) as source:
            image = source.convert("RGBA")
        red, green, blue, alpha = image.getpixel((6, 6))
        image.putpixel((6, 6), ((red + 17) % 255, green, blue, alpha))
        image.save(path, format="PNG")

    def mutate_json(self, path: Path) -> None:
        value = json.loads(path.read_text(encoding="utf-8"))
        value["golden_mutation"] = True
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def refresh_export_artifacts(
        self,
        report_path: Path,
        report: dict[str, object],
    ) -> None:
        for field in ("gif", "preview"):
            record = report.get(field)
            if not isinstance(record, dict):
                continue
            path = report_path.parent / str(record["path"])
            record["sha256"] = sha256_path(path)
            record["bytes"] = path.stat().st_size
        report["artifact_fingerprint"] = report_artifact_fingerprint(
            report_path,
            report,
        )

    def validation_command(self, report: Path) -> list[object]:
        arguments: list[object] = [report, "--status", "pass"]
        for name, note in NOTES.items():
            arguments.extend([f"--{name.replace('_', '-')}", note])
        return arguments

    def test_fixture_motion_and_keyframes_export_end_to_end(self) -> None:
        self.doctor("healthy", "motion", FIXTURE / "motion.json")
        self.doctor("healthy", cwd=FIXTURE)
        with tempfile.TemporaryDirectory() as temporary:
            package, export_report = self.build_passed_scenario(
                Path(temporary),
                "keyframes",
            )
            self.assertTrue((package / "sticker.webp").is_file())
            self.assertTrue((export_report.parent / "sticker.gif").is_file())
            self.doctor("healthy", cwd=export_report.parent)

    def test_render_track_export_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, export_report = self.build_passed_scenario(
                Path(temporary),
                "render",
            )
            report = json.loads(export_report.read_text(encoding="utf-8"))
            self.assertEqual(report["frame_track"], "render")
            self.assertEqual(report["gif"]["selected_fps"], 5)
            self.assertTrue(
                (package / "validation" / "render-report.json").is_file()
            )

    def test_export_doctor_rejects_tampered_evidence_and_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, export_report = self.build_passed_scenario(
                Path(temporary),
                "keyframes",
            )
            original = json.loads(export_report.read_text(encoding="utf-8"))
            mutations = {
                "technical-evidence": lambda report: report[
                    "technical_validation"
                ].__setitem__("checks", {"placeholder": True}),
                "provenance-and-limit": lambda report: (
                    report.pop("spec_url"),
                    report.__setitem__("verified_on", "2999-01-01"),
                    report["gif"].__setitem__("max_bytes", 1),
                ),
            }
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    report = json.loads(json.dumps(original))
                    mutate(report)
                    export_report.write_text(
                        json.dumps(report),
                        encoding="utf-8",
                    )
                    self.doctor("invalid", "export", export_report)

    def test_export_doctor_revalidates_upstream_report_evidence(self) -> None:
        cases = (
            ("keyframes", "validation/report.json", "source_validation_report"),
            ("render", "validation/render-report.json", "track_report"),
        )
        for track, relative_report, binding_key in cases:
            with self.subTest(track=track), tempfile.TemporaryDirectory() as temporary:
                package, export_report = self.build_passed_scenario(
                    Path(temporary),
                    track,
                )
                upstream_report = package / relative_report
                upstream = json.loads(upstream_report.read_text(encoding="utf-8"))
                upstream["technical_validation"]["checks"] = {
                    "placeholder": True
                }
                upstream_report.write_text(
                    json.dumps(upstream),
                    encoding="utf-8",
                )
                report = json.loads(export_report.read_text(encoding="utf-8"))
                report[binding_key]["sha256"] = hashlib.sha256(
                    upstream_report.read_bytes()
                ).hexdigest()
                export_report.write_text(
                    json.dumps(report),
                    encoding="utf-8",
                )

                self.doctor("invalid", "export", export_report)

    def test_export_doctor_reopens_upstream_media(self) -> None:
        cases = (
            (
                "keyframes",
                "source/frames/000.png",
                "validation/report.json",
                "source_validation_report",
                package_fingerprint,
            ),
            (
                "render",
                "source/rendered-frames/0000.png",
                "validation/render-report.json",
                "track_report",
                render_track_fingerprint,
            ),
        )
        for track, frame_relative, report_relative, binding_key, fingerprint in cases:
            with self.subTest(track=track), tempfile.TemporaryDirectory() as temporary:
                package, export_report = self.build_passed_scenario(
                    Path(temporary),
                    track,
                )
                frame_path = package / frame_relative
                blank = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
                blank.save(frame_path, format="PNG")

                upstream_path = package / report_relative
                upstream = json.loads(upstream_path.read_text(encoding="utf-8"))
                upstream["frames"][0] = alpha_metrics(blank)
                upstream["artifact_fingerprint"] = fingerprint(package)
                upstream_path.write_text(
                    json.dumps(upstream),
                    encoding="utf-8",
                )

                report = json.loads(export_report.read_text(encoding="utf-8"))
                report[binding_key]["sha256"] = sha256_path(upstream_path)
                if binding_key == "source_validation_report":
                    report[binding_key]["artifact_fingerprint"] = upstream[
                        "artifact_fingerprint"
                    ]
                export_report.write_text(
                    json.dumps(report),
                    encoding="utf-8",
                )

                self.doctor("invalid", "export", export_report)

    def test_export_doctor_rejects_invalid_preview_alpha(self) -> None:
        variants = {
            "blank": Image.new("RGBA", (32, 32), (0, 0, 0, 0)),
            "opaque-border": Image.new("RGBA", (32, 32), (220, 30, 30, 255)),
        }
        with tempfile.TemporaryDirectory() as temporary:
            _, export_report = self.build_passed_scenario(
                Path(temporary),
                "keyframes",
            )
            original = json.loads(export_report.read_text(encoding="utf-8"))
            preview_path = export_report.parent / "preview.png"
            for name, image in variants.items():
                with self.subTest(name=name):
                    image.save(preview_path, format="PNG")
                    report = json.loads(json.dumps(original))
                    preview = report["preview"]
                    assert isinstance(preview, dict)
                    preview["bytes"] = preview_path.stat().st_size
                    preview["sha256"] = sha256_path(preview_path)
                    self.refresh_export_artifacts(export_report, report)
                    export_report.write_text(
                        json.dumps(report),
                        encoding="utf-8",
                    )

                    self.doctor("invalid", "export", export_report)

    def test_keyframe_invalidation_chain(self) -> None:
        for mutation in ("authored-frame", "source-report", "export-gif"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                package, export_report = self.build_passed_scenario(
                    Path(temporary),
                    "keyframes",
                )
                if mutation == "authored-frame":
                    self.mutate_png(package / "source" / "frames" / "000.png")
                    self.doctor("invalid", "package", package)
                    result = self.run_cli(
                        EXPORT_SCRIPT,
                        "--package",
                        package,
                        "--platform",
                        "gif89a-fixture-mutated",
                        "--size",
                        "32x32",
                        "--spec-url",
                        SPEC_URL,
                        "--verified-on",
                        VERIFIED_ON,
                    )
                elif mutation == "source-report":
                    self.mutate_json(package / "validation" / "report.json")
                    self.doctor("invalid", "export", export_report)
                    result = self.run_cli(
                        VALIDATION_SCRIPT,
                        *self.validation_command(export_report),
                    )
                else:
                    (export_report.parent / "sticker.gif").write_bytes(
                        (export_report.parent / "sticker.gif").read_bytes()
                        + b"golden-mutation"
                    )
                    self.doctor("invalid", "export", export_report)
                    result = self.run_cli(
                        VALIDATION_SCRIPT,
                        *self.validation_command(export_report),
                    )
                self.assertNotEqual(result.returncode, 0)

    def test_render_invalidation_chain(self) -> None:
        for mutation in ("render-frame", "render-report", "export-gif"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                package, export_report = self.build_passed_scenario(
                    Path(temporary),
                    "render",
                )
                if mutation == "render-frame":
                    self.mutate_png(
                        package / "source" / "rendered-frames" / "0000.png"
                    )
                    self.doctor("invalid", "package", package)
                    result = self.run_cli(
                        EXPORT_SCRIPT,
                        "--package",
                        package,
                        "--platform",
                        "gif89a-fixture-mutated",
                        "--size",
                        "32x32",
                        "--frame-track",
                        "render",
                        "--track-report",
                        package / "validation" / "render-report.json",
                        "--fps-candidates",
                        "5",
                        "--spec-url",
                        SPEC_URL,
                        "--verified-on",
                        VERIFIED_ON,
                    )
                elif mutation == "render-report":
                    self.mutate_json(
                        package / "validation" / "render-report.json"
                    )
                    self.doctor("invalid", "export", export_report)
                    result = self.run_cli(
                        VALIDATION_SCRIPT,
                        *self.validation_command(export_report),
                    )
                else:
                    (export_report.parent / "sticker.gif").write_bytes(
                        (export_report.parent / "sticker.gif").read_bytes()
                        + b"golden-mutation"
                    )
                    self.doctor("invalid", "export", export_report)
                    result = self.run_cli(
                        VALIDATION_SCRIPT,
                        *self.validation_command(export_report),
                    )
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
