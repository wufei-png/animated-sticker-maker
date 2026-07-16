from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from support import chroma_key


class ChromaKeyTests(unittest.TestCase):
    def test_explicit_zero_threshold_is_not_replaced_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            output = root / "output.png"
            image = Image.new("RGB", (4, 4), (255, 0, 255))
            image.putpixel((2, 2), (250, 0, 255))
            image.save(source)
            argv = [
                "chroma_key.py",
                str(source),
                str(output),
                "--key",
                "#FF00FF",
                "--transparent-threshold",
                "0",
            ]
            with mock.patch.object(sys, "argv", argv):
                chroma_key.main()
            with Image.open(output) as result:
                self.assertGreater(result.getpixel((2, 2))[3], 0)


if __name__ == "__main__":
    unittest.main()
