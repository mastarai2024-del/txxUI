import hashlib
import importlib.util
import json
import subprocess
import sys
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

    def test_pairs_keep_sources_and_place_before_left_after_right(self):
        before = self.picture("before.png", (200, 400), "red")
        after = self.picture("after.png", (200, 400), "blue")
        sources = [before, after]
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        output = self.directory / "paired.png"
        data = module.build_pairs([
            {"state": "设置开启", "before": before, "after": after,
             "changes": ["调整标签"]}
        ], output, thumb_width=80)
        self.assertEqual(data["mode"], "pairs")
        self.assertEqual(data["pairs"][0]["state"], "设置开启")
        self.assertEqual(data["pairs"][0]["changes"], ["调整标签"])
        self.assertEqual([item["role"] for item in data["images"]], ["before", "after"])
        self.assertEqual([item["thumbnail_size"] for item in data["images"]], [[80, 160]] * 2)
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources])
        self.assertEqual(json.loads(output.with_suffix(".json").read_text()), data)
        with Image.open(output) as image:
            self.assertEqual(image.getpixel((13, 41)), (255, 0, 0))
            self.assertEqual(image.getpixel((105, 41)), (0, 0, 255))

    def test_pairs_reject_different_dimensions_without_outputs(self):
        before = self.picture("before.png", (200, 400))
        after = self.picture("after.png", (400, 200))
        output = self.directory / "paired.png"
        with self.assertRaisesRegex(ValueError, "dimensions"):
            module.build_pairs([{"state": "settings", "before": before, "after": after}], output)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".json").exists())

    def test_pairs_validate_later_images_before_writing(self):
        before = self.picture("before.png", (20, 20))
        after = self.picture("after.png", (20, 20), "blue")
        bad = self.directory / "broken.png"
        bad.write_text("invalid screenshot")
        output = self.directory / "paired.png"
        with self.assertRaises(OSError):
            module.build_pairs([
                {"state": "first", "before": before, "after": after},
                {"state": "second", "before": before, "after": bad},
            ], output)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_suffix(".json").exists())

    def test_pairs_reject_ambiguous_mapping_and_source_overwrite(self):
        before = self.picture("before.png", (20, 20))
        after = self.picture("after.png", (20, 20), "blue")
        pair = {"state": "settings", "before": before, "after": after}
        output = self.directory / "paired.png"
        with self.assertRaisesRegex(ValueError, "unique"):
            module.build_pairs([pair, pair], output)
        with self.assertRaisesRegex(ValueError, "different"):
            module.build_pairs([{**pair, "after": before}], output)
        original = before.read_bytes()
        with self.assertRaises(ValueError):
            module.build_pairs([pair], before, overwrite=True)
        self.assertEqual(before.read_bytes(), original)
        self.assertFalse(output.exists())

    def test_pairs_cli_resolves_paths_relative_to_manifest(self):
        self.picture("before.png", (20, 20))
        self.picture("after.png", (20, 20), "blue")
        manifest = self.directory / "pairs.json"
        manifest.write_text(json.dumps({"pairs": [
            {"state": "settings", "before": "before.png", "after": "after.png"}
        ]}))
        output = self.directory / "result/paired.png"
        result = subprocess.run([
            sys.executable, "-B", str(ROOT / "scripts/contact_sheet.py"),
            "--pairs", str(manifest), "--output", str(output),
        ], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["pairs"], 1)
        index = json.loads(output.with_suffix(".json").read_text())
        self.assertEqual(index["pairs"][0]["before"], str(self.directory / "before.png"))

    def test_pairs_cli_cannot_overwrite_its_manifest(self):
        self.picture("before.png", (20, 20))
        self.picture("after.png", (20, 20), "blue")
        manifest = self.directory / "manifest.png"
        original = json.dumps({"pairs": [
            {"state": "settings", "before": "before.png", "after": "after.png"}
        ]})
        manifest.write_text(original)
        result = subprocess.run([
            sys.executable, "-B", str(ROOT / "scripts/contact_sheet.py"),
            "--pairs", str(manifest), "--output", str(manifest), "--overwrite",
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(manifest.read_text(), original)


if __name__ == "__main__":
    unittest.main()
