import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from parsers import inspect
from parsers.common import OK

SAMPLES = os.path.join(ROOT, "tests", "samples")


def load_manifest():
    with open(os.path.join(SAMPLES, "manifest.json"), encoding="utf-8") as file:
        return json.load(file)


class ParserTests(unittest.TestCase):
    def test_samples(self):
        manifest = load_manifest()
        try:
            from PIL import Image
        except ImportError:
            Image = None
        for name, expected in manifest.items():
            with self.subTest(file=name):
                info = inspect(os.path.join(SAMPLES, name))
                self.assertEqual(info.status, expected.get("status", OK), info.problem)
                if "kind" in expected:
                    self.assertEqual(info.kind, expected["kind"])
                if "problem" in expected:
                    self.assertIn(expected["problem"], info.problem)
                if info.status != OK:
                    continue
                if "bits" in expected:
                    self.assertTrue(info.depth.startswith(f"{expected['bits']} бит"), info.depth)
                if "dpi" in expected:
                    self.assertTrue(info.dpi.startswith(str(expected["dpi"])), info.dpi)
                if "compression" in expected:
                    self.assertIn(expected["compression"], info.compression)
                if "frames" in expected:
                    self.assertTrue(info.extra["Кадров"].startswith(str(expected["frames"])))
                if "pages" in expected:
                    self.assertEqual(info.extra["Страниц (IFD)"], str(expected["pages"]))
                if "width" in expected:
                    self.assertEqual((info.width, info.height), (expected["width"], expected["height"]))
                elif Image is not None:
                    with Image.open(os.path.join(SAMPLES, name)) as image:
                        self.assertEqual((info.width, info.height), image.size)

    def test_teacher_folder(self):
        folder = os.path.join(ROOT, "tests", "Для проверки Lab2")
        if not os.path.isdir(folder):
            self.skipTest("нет папки с файлами преподавателя")
        for name in sorted(os.listdir(folder)):
            with self.subTest(file=name):
                info = inspect(os.path.join(folder, name))
                self.assertEqual(info.status, OK, info.problem)
                self.assertEqual(info.kind, "BMP")
                self.assertTrue(info.width > 0 and info.height > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
