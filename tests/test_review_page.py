from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from support import review_page


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "skills" / "animated-sticker-maker" / "scripts"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "golden_workflow"
PACKAGE_SCRIPT = SCRIPTS / "package_sticker.py"
VALIDATION_SCRIPT = SCRIPTS / "record_visual_validation.py"
EXPORT_SCRIPT = SCRIPTS / "export_platform_gif.py"
REVIEW_SCRIPT = SCRIPTS / "generate_review.py"
SPEC_URL = "https://www.w3.org/Graphics/GIF/spec-gif89a.txt"
VERIFIED_ON = "1990-07-31"
NOTES = {
    "identity": "Synthetic tile remains recognizable.",
    "meaning": "Forward lean and hold remain clear.",
    "loop": "Return connects cleanly.",
    "alpha": "Transparent border remains clean.",
    "small-size": "Primary tile remains readable.",
}


class ReviewPageTests(unittest.TestCase):
    def run_cli(
        self,
        script: Path,
        *arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *(str(value) for value in arguments)],
            text=True,
            capture_output=True,
            check=False,
        )

    def require_success(
        self,
        script: Path,
        *arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        result = self.run_cli(script, *arguments)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def package_fixture(
        self,
        root: Path,
        *,
        include_reference: bool = False,
        frames_dir: Path | None = None,
    ) -> Path:
        package = root / "package"
        arguments: list[object] = [
            "--frames-dir",
            frames_dir or FIXTURE / "frames",
            "--motion",
            FIXTURE / "motion.json",
            "--reference-image",
            FIXTURE / "reference.png",
            "--output",
            package,
            "--expected-size",
            "16x16",
        ]
        if include_reference:
            arguments.append("--include-reference")
        self.require_success(PACKAGE_SCRIPT, *arguments)
        return package

    def record_visual_validation(self, report: Path) -> None:
        arguments: list[object] = [report, "--status", "pass"]
        for name, note in NOTES.items():
            arguments.extend([f"--{name.replace('_', '-')}", note])
        self.require_success(VALIDATION_SCRIPT, *arguments)

    def export_fixture(
        self,
        package: Path,
        *,
        track: str = "keyframes",
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

    def test_overview_samples_at_most_twenty_four_frames(self) -> None:
        indices = review_page.overview_indices(240)

        self.assertEqual(len(indices), 24)
        self.assertEqual(indices[0], 0)
        self.assertEqual(indices[-1], 239)
        self.assertEqual(indices, sorted(set(indices)))

    def test_all_report_scopes_generate_one_visual_language(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package_fixture(Path(temporary))
            reports = [
                package / "validation" / "report.json",
                package / "validation" / "render-report.json",
            ]
            for report in reports:
                self.require_success(
                    REVIEW_SCRIPT,
                    report,
                    "--reference-image",
                    FIXTURE / "reference.png",
                )

            self.record_visual_validation(reports[0])
            export_report = self.export_fixture(package)
            self.require_success(
                REVIEW_SCRIPT,
                export_report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            reports.append(export_report)

            expected_scopes = (
                "package_source",
                "render_track",
                "export_files",
            )
            for report, scope in zip(reports, expected_scopes):
                output = report.with_name(f"{report.stem}.review.html")
                html = output.read_text(encoding="utf-8")
                self.assertIn("Animation inspection light table", html)
                self.assertIn('"scope":"' + scope + '"', html)
                self.assertIn("data:image/png;base64,", html)
                self.assertIn("Exposure rail", html)
                self.assertIn("Visual review prompts", html)

    def test_render_export_uses_render_track_inspector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package_fixture(Path(temporary))
            self.record_visual_validation(
                package / "validation" / "report.json"
            )
            self.record_visual_validation(
                package / "validation" / "render-report.json"
            )
            export_report = self.export_fixture(
                package,
                track="render",
                platform="gif89a-render",
            )

            self.require_success(
                REVIEW_SCRIPT,
                export_report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            html = export_report.with_name(
                "sticker.export-report.review.html"
            ).read_text(encoding="utf-8")

            self.assertIn(
                '{"label":"Frame track","value":"render"}',
                html,
            )
            self.assertIn('"label":"Render track inspector"', html)
            self.assertIn("use the selected-track inspector", html)
            self.assertIn('"label":"Authored semantic anchors"', html)

    def test_stale_or_wrong_reference_does_not_replace_existing_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.package_fixture(root)
            report = package / "validation" / "report.json"
            output = report.with_name("report.review.html")
            self.require_success(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            original = output.read_bytes()

            wrong_reference = root / "wrong.png"
            Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(
                wrong_reference,
                format="PNG",
            )
            result = self.run_cli(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                wrong_reference,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), original)

            frame = package / "source" / "frames" / "000.png"
            frame.write_bytes(frame.read_bytes() + b"stale-review")
            result = self.run_cli(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), original)

    def test_included_reference_is_automatic_and_cannot_be_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package_fixture(
                Path(temporary),
                include_reference=True,
            )
            report = package / "validation" / "report.json"
            self.require_success(REVIEW_SCRIPT, report)
            html = report.with_name("report.review.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("Included package reference", html)
            self.assertIn(
                '"src":"../source/reference/reference.png"',
                html,
            )

            result = self.run_cli(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            self.assertNotEqual(result.returncode, 0)

    def test_technical_failure_can_still_generate_a_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames = root / "frames"
            shutil.copytree(FIXTURE / "frames", frames)
            with Image.open(frames / "000.png") as source:
                source.convert("RGB").save(frames / "000.png", format="PNG")
            output = root / "package"
            result = self.run_cli(
                PACKAGE_SCRIPT,
                "--frames-dir",
                frames,
                "--motion",
                FIXTURE / "motion.json",
                "--reference-image",
                FIXTURE / "reference.png",
                "--output",
                output,
                "--expected-size",
                "16x16",
            )
            self.assertEqual(result.returncode, 2)
            failed = output.with_name("package.failed")
            report = failed / "validation" / "report.json"

            self.require_success(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            html = report.with_name("report.review.html").read_text(
                encoding="utf-8"
            )
            self.assertIn('"technical_status":"fail"', html)
            self.assertIn("Encoded package unavailable", html)

    def test_output_must_stay_beside_the_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.package_fixture(root)
            report = package / "validation" / "report.json"

            result = self.run_cli(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
                "--output",
                root / "outside.html",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "outside.html").exists())


if __name__ == "__main__":
    unittest.main()
