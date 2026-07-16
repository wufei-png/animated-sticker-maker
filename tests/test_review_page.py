from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from support import review_page
from review_template import render_review_html


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
        motion: Path | None = None,
    ) -> Path:
        package = root / "package"
        arguments: list[object] = [
            "--frames-dir",
            frames_dir or FIXTURE / "frames",
            "--motion",
            motion or FIXTURE / "motion.json",
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

        with_required = review_page.overview_indices(
            240,
            required_index=117,
        )
        self.assertEqual(len(with_required), 24)
        self.assertIn(117, with_required)

    def test_review_language_is_limited_to_built_in_dictionaries(self) -> None:
        self.assertEqual(review_page.language_text("en")["html_lang"], "en")
        self.assertEqual(review_page.language_text("zh")["html_lang"], "zh-CN")
        with self.assertRaisesRegex(ValueError, "must be 'en' or 'zh'"):
            review_page.language_text("fr")

    def test_static_template_replacements_do_not_change_report_payload(self) -> None:
        html = render_review_html(
            {
                "text": {
                    "html_lang": "en",
                    "document_title": "Placeholder regression",
                },
                "report_note": "__HTML_LANG__ / __DOCUMENT_TITLE__",
            }
        )

        self.assertIn(
            '"report_note":"__HTML_LANG__ / __DOCUMENT_TITLE__"',
            html,
        )

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

    def test_encoded_package_uses_decoded_artifact_player(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package_fixture(Path(temporary))
            report = package / "validation" / "report.json"
            output = report.with_name("report.review.html")

            self.require_success(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            model = review_page.build_review_model(
                report,
                reference_image=FIXTURE / "reference.png",
                output_path=output,
            )
            html = output.read_text(encoding="utf-8")

            self.assertNotIn("schema_version", model)
            self.assertNotIn(str(package.resolve()), html)
            self.assertNotIn(str(report.resolve()), html)
            self.assertEqual(
                [frame["duration_ms"] for frame in model["inspector"]["frames"]],
                [200, 200, 600, 200],
            )
            self.assertEqual(model["semantic_hold"]["primary_index"], 2)
            self.assertTrue(
                all(
                    frame["src"].startswith("data:image/png;base64,")
                    for frame in model["inspector"]["frames"]
                )
            )
            self.assertIn(
                '"label":"Decoded encoded-artifact inspector"',
                html,
            )
            self.assertIn('"label":"E0001"', html)
            self.assertIn('"path":"sticker.webp#frame=1"', html)
            self.assertIn("Post-encode artifact authority", html)
            self.assertIn("Actual size · 50 × 50", html)
            self.assertIn("Inspection zoom · 5×", html)
            self.assertIn("Jump to semantic hold", html)
            self.assertIn(
                "It is an inspection anchor, not an automatic playback pause.",
                html,
            )
            self.assertIn(
                "Declared by motion.semantic_hold_frame",
                html,
            )
            self.assertNotIn("Restart encoded playback", html)
            self.assertNotIn(
                'create("h3", "", REVIEW_DATA.semantic_hold',
                html,
            )

    def test_agent_can_generate_a_chinese_review_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package_fixture(Path(temporary))
            report = package / "validation" / "report.json"
            output = report.with_name("report.zh.review.html")

            self.require_success(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
                "--language",
                "zh",
                "--output",
                output.name,
            )
            html = output.read_text(encoding="utf-8")

            self.assertIn('<html lang="zh-CN">', html)
            self.assertIn("<title>动态贴纸曝光审核</title>", html)
            self.assertIn('"language":"zh"', html)
            self.assertIn('"scope_label":"编码后产物"', html)
            self.assertIn("语义停留点（HOLD）", html)
            self.assertIn("它是审核锚点，不会让动画在此自动暂停", html)
            self.assertIn("位置来自 motion.semantic_hold_frame", html)
            self.assertIn("真实尺寸 · 50 × 50", html)
            self.assertNotIn(">Review evidence<", html)

    def test_chinese_review_localizes_every_report_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package_fixture(Path(temporary))
            reports = [
                (
                    package / "validation" / "report.json",
                    "编码后产物",
                ),
                (
                    package / "validation" / "render-report.json",
                    "编码前渲染轨道",
                ),
            ]
            self.record_visual_validation(reports[0][0])
            export_report = self.export_fixture(package)
            reports.append((export_report, "编码后平台衍生物"))

            for index, (report, scope_label) in enumerate(reports):
                output_name = f"scope-{index}.review.html"
                self.require_success(
                    REVIEW_SCRIPT,
                    report,
                    "--reference-image",
                    FIXTURE / "reference.png",
                    "--language",
                    "zh",
                    "--output",
                    output_name,
                )
                html = report.with_name(output_name).read_text(encoding="utf-8")
                self.assertIn(f'"scope_label":"{scope_label}"', html)
                self.assertIn('"language":"zh"', html)
                self.assertIn("语义停留点（HOLD）", html)

    def test_chinese_review_explains_semantic_hold_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            motion = json.loads(
                (FIXTURE / "motion.json").read_text(encoding="utf-8")
            )
            motion.pop("semantic_hold_frame")
            motion_path = root / "motion-without-hold.json"
            shutil.copytree(FIXTURE / "render", root / "render")
            motion_path.write_text(
                json.dumps(motion, ensure_ascii=False),
                encoding="utf-8",
            )
            package = self.package_fixture(root, motion=motion_path)
            report = package / "validation" / "report.json"

            self.require_success(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
                "--language",
                "zh",
            )
            html = report.with_name("report.review.html").read_text(
                encoding="utf-8"
            )

            self.assertIn('"declared":false', html)
            self.assertIn('"primary_index":2', html)
            self.assertIn(
                "未声明 semantic_hold_frame，因此回退为持续时间最长关键帧的中点",
                html,
            )

    def test_english_is_the_default_review_language(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.package_fixture(Path(temporary))
            report = package / "validation" / "report.json"

            self.require_success(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            html = report.with_name("report.review.html").read_text(
                encoding="utf-8"
            )

            self.assertIn('<html lang="en">', html)
            self.assertIn("<title>Animated sticker exposure review</title>", html)
            self.assertIn('"language":"en"', html)
            self.assertIn("Semantic hold", html)

    def test_review_explains_explicit_nonstandard_policy_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            motion = json.loads(
                (FIXTURE / "motion.json").read_text(encoding="utf-8")
            )
            motion.pop("render", None)
            for frame in motion["frames"]:
                frame["duration_ms"] = 600
            motion_path = root / "nonstandard-motion.json"
            motion_path.write_text(json.dumps(motion), encoding="utf-8")
            package = root / "package"
            self.require_success(
                PACKAGE_SCRIPT,
                "--frames-dir",
                FIXTURE / "frames",
                "--motion",
                motion_path,
                "--reference-image",
                FIXTURE / "reference.png",
                "--output",
                package,
                "--expected-size",
                "16x16",
                "--allow-nonstandard-timing",
            )
            report = package / "validation" / "report.json"

            self.require_success(
                REVIEW_SCRIPT,
                report,
                "--reference-image",
                FIXTURE / "reference.png",
            )
            html = report.with_name("report.review.html").read_text(
                encoding="utf-8"
            )

            self.assertIn("OUTSIDE DEFAULT · ALLOWED", html)
            self.assertIn("Explicit policy overrides", html)
            self.assertIn("--allow-nonstandard-timing", html)
            self.assertIn('"actual":2400', html)
            self.assertIn('"default_range":[1200,2000]', html)

    def test_render_export_uses_decoded_gif_with_render_comparison(self) -> None:
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
            self.assertIn(
                '"label":"Decoded encoded-artifact inspector"',
                html,
            )
            self.assertIn(
                '"label":"Selected source-track comparison"',
                html,
            )
            self.assertIn('"label":"R0001"', html)
            self.assertIn("Post-encode artifact authority", html)

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
