import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contact_sheet", ROOT / "scripts/contact_sheet.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ContactSheetTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".private"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="test-", dir=private)
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def picture(self, name, size, color="red", mode="RGB"):
        path = self.directory / name
        Image.new(mode, size, color).save(path)
        return path

    def test_multiple_sizes_keep_ratio_and_original_bytes(self):
        a = self.picture("a.png", (200, 400))
        b = self.picture("b.png", (400, 200), "blue")
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in [a, b]]
        output = self.directory / "review/sheet.png"
        data = module.build_sheet([a, b], output, columns=2, thumb_width=100)
        self.assertEqual([x["thumbnail_size"] for x in data["images"]], [[100, 200], [100, 50]])
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in [a, b]])
        self.assertEqual(json.loads(output.with_suffix(".json").read_text()), data)
        with Image.open(output) as image:
            self.assertEqual(list(image.size), data["size"])
            self.assertEqual(image.getpixel((13, 41)), (255, 0, 0))

    def test_transparent_input_composites_on_white(self):
        a = self.picture("transparent.png", (20, 20), (0, 0, 0, 0), "RGBA")
        output = self.directory / "sheet.png"
        module.build_sheet([a], output)
        with Image.open(output) as image:
            self.assertEqual(image.getpixel((13, 41)), (255, 255, 255))

    def test_refuses_existing_outputs_and_source_overwrite(self):
        a = self.picture("a.png", (20, 20))
        output = self.directory / "sheet.png"
        module.build_sheet([a], output)
        original = output.read_bytes()
        with self.assertRaises(FileExistsError):
            module.build_sheet([a], output)
        with self.assertRaises(ValueError):
            module.build_sheet([a], a, overwrite=True)
        self.assertEqual(output.read_bytes(), original)

    def test_bad_input_does_not_write_partial_output(self):
        a = self.picture("a.png", (20, 20))
        bad = self.directory / "bad.png"
        bad.write_text("not an image")
        output = self.directory / "sheet.png"
        with self.assertRaises(OSError):
            module.build_sheet([a, bad], output)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".json").exists())


if __name__ == "__main__":
    unittest.main()
