from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "animated-sticker-maker"
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_script(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package_sticker = load_script("package_sticker")
export_platform_gif = load_script("export_platform_gif")
record_visual_validation = load_script("record_visual_validation")
artifact_integrity = load_script("artifact_integrity")
chroma_key = load_script("chroma_key")
motion_schema = load_script("motion_schema")


def make_frame(path: Path, color: tuple[int, int, int, int], size: int = 16) -> None:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y in range(2, size - 2):
        for x in range(2, size - 2):
            image.putpixel((x, y), color)
    image.save(path)


def motion_plan(
    frames: list[dict[str, object]], **overrides: object
) -> dict[str, object]:
    motion: dict[str, object] = {
        "schema_version": 2,
        "id": "test-sticker",
        "prompt": "Test motion",
        "reference_image": "reference.png",
        "canvas": [16, 16],
        "resampling": "lanczos",
        "loop": True,
        "identity_lock": {
            "subject": "Test subject",
            "fixed": ["silhouette"],
            "flexible": [],
            "forbidden": [],
        },
        "generation_plan": {"anchors": [], "deterministic": ["timing"]},
        "transparency": {"strategy": "existing-alpha", "work_color": None},
        "frames": [
            {
                **frame,
                "description": frame.get("description", f"Frame {index}"),
            }
            for index, frame in enumerate(frames)
        ],
    }
    motion.update(overrides)
    return motion


def packaged_motion(
    frames: list[dict[str, object]], **overrides: object
) -> dict[str, object]:
    motion = motion_plan(frames, **overrides)
    motion.pop("reference_image")
    motion["reference"] = {
        "filename": "reference.png",
        "sha256": "0" * 64,
        "included_path": None,
    }
    return motion
