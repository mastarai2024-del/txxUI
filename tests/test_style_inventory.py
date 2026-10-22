import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("style_inventory", ROOT / "scripts/style_inventory.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def frame(root_id, content="", style="width: 375px; height: 812px; background: #F3F3F3"):
    return f'<div data-node-id="{root_id}" data-name="Private business title" style="{style}">{content}</div>'


def label(node_id, style="font-size: 14px; line-height: 20px; color: #333333"):
    return f'<span data-node-id="{node_id}" style="{style}">Private user text</span>'


class StyleInventoryTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".private"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="inventory-test-", dir=private)
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.output = self.directory / "inventory.json"

    def snapshot(self, name, codes, single=False):
        if single:
            text = "Success\n代码内容：\n\n" + codes[0]
        else:
            fence = chr(96) * 3
            text = "Success\n" + "\n".join(f"### [{i}] Name\n\n{fence}html\n{code}\n{fence}" for i, code in enumerate(codes, 1))
        path = self.directory / name
        path.write_text(json.dumps({"content": [{"type": "text", "text": text}]}))
        return path

    def manifest(self, entries):
        path = self.directory / "manifest.json"
        path.write_text(json.dumps({"sources": entries}))
        return path

    def source(self, root_id, family="form", role="designer-final", snapshot="snapshot.json"):
        return {"root_id": root_id, "family": family, "role": role, "snapshot": snapshot}

    def test_explicit_whitelist_excludes_prototype_ai_legacy_and_uncertain(self):
        self.snapshot("snapshot.json", [frame(f"1:{i}", label(f"2:{i}")) for i in range(1, 7)])
        roles = ["designer-final", "prototype", "ai-comparison", "legacy", "uncertain", "spec"]
        manifest = self.manifest([self.source(f"1:{i}", role=role) for i, role in enumerate(roles, 1)])
        data = module.build_inventory(manifest, self.output)
        self.assertEqual(data["counts"], {"included_roots": 2, "excluded_roots": 4, "measured_nodes": 4})
        self.assertEqual({x["root_id"] for x in data["nodes"]}, {"1:1", "1:6"})
        self.assertEqual({x["role"] for x in data["summary"]}, {"designer-final", "spec"})
        encoded = self.output.read_text()
        self.assertNotIn("Private", encoded)
        self.assertNotIn("data-name", encoded)

    def test_repeated_states_and_duplicate_manifest_do_not_inflate_families(self):
        self.snapshot("snapshot.json", [frame(f"1:{i}", label(f"2:{i}")) for i in range(1, 4)])
        entries = [self.source("1:1"), self.source("1:1"), self.source("1:2"), self.source("1:3", family="list")]
        data = module.build_inventory(self.manifest(entries), self.output)
        size = next(x for x in data["summary"] if x["property"] == "font-size")
        self.assertEqual(size["occurrences"], 3)
        self.assertEqual(size["independent_families"], 2)
        self.assertEqual(size["families"], ["form", "list"])
        self.assertEqual(data["counts"]["included_roots"], 3)

    def test_single_and_multi_snapshots_and_overlapping_roots_are_deduplicated(self):
        child = frame("1:2", label("2:1") + '<img src="./asset/icon.svg" />')
        self.snapshot("snapshot.json", [frame("1:1", child), child])
        self.snapshot("single.json", [frame("3:1", label("4:1"))], single=True)
        data = module.build_inventory(self.manifest([
            self.source("1:1"), self.source("1:2"), self.source("3:1", snapshot="single.json")
        ]), self.output)
        self.assertEqual(len(data["nodes"]), 6)
        self.assertEqual(sum(x["node_id"] == "1:2" for x in data["nodes"]), 1)
        self.assertEqual(sum(x["tag"] == "img" for x in data["nodes"]), 1)

    def test_overlapping_node_conflicts_are_not_silently_combined(self):
        self.snapshot("snapshot.json", [frame("1:1", frame("1:2")), frame("1:2")])
        with self.assertRaisesRegex(ValueError, "conflicting role/family"):
            module.build_inventory(self.manifest([self.source("1:1"), self.source("1:2", family="list")]), self.output)
        self.snapshot("snapshot.json", [frame("1:1", frame("1:2")), frame("1:2", style="width: 99px")])
        with self.assertRaisesRegex(ValueError, "conflicting exported properties"):
            module.build_inventory(self.manifest([self.source("1:1"), self.source("1:2")]), self.output)
        self.assertFalse(self.output.exists())

    def test_excluded_child_cannot_pollute_an_included_parent(self):
        child = frame("1:2", label("2:1", style="font-size: 99px"))
        self.snapshot("snapshot.json", [frame("1:1", child), child])
        for parent_role, child_role in (
            ("designer-final", "ai-comparison"), ("prototype", "designer-final")
        ):
            entries = [self.source("1:1", role=parent_role), self.source("1:2", role=child_role)]
            for order in (entries, entries[::-1]):
                with self.subTest(parent_role=parent_role, child_role=child_role, child_first=order is not entries):
                    with self.assertRaisesRegex(ValueError, "Included and excluded source subtrees overlap"):
                        module.build_inventory(self.manifest(order), self.output)
                    self.assertFalse(self.output.exists())

    def test_byte_identical_snapshot_copies_cannot_hide_role_overlap(self):
        child = frame("1:2")
        first = self.snapshot("snapshot.json", [frame("1:1", child), child])
        (self.directory / "copy.json").write_bytes(first.read_bytes())
        with self.assertRaisesRegex(ValueError, "subtrees overlap"):
            module.build_inventory(self.manifest([
                self.source("1:1"), self.source("1:2", role="legacy", snapshot="copy.json")
            ]), self.output)
        self.assertFalse(self.output.exists())

    def test_svg_and_absent_dimensions_stay_unknown_and_asset_urls_are_removed(self):
        content = '<div data-node-id="2:1"><img src="https://private.invalid/icon.svg?token=secret" style="color: #999999" /></div>'
        self.snapshot("snapshot.json", [frame("1:1", content, style="background: url(https://private.invalid/a.png)")])
        data = module.build_inventory(self.manifest([self.source("1:1")]), self.output)
        image = next(x for x in data["nodes"] if x["tag"] == "img")
        self.assertIsNone(image["node_id"])
        self.assertIn("width:not-explicit", image["unknown"])
        self.assertIn("height:not-explicit", image["unknown"])
        self.assertIn("svg-geometry:not-inspected", image["unknown"])
        self.assertNotIn("width", image["properties"])
        self.assertIn("background:asset-reference", data["nodes"][0]["unknown"])
        self.assertNotIn("private.invalid", self.output.read_text())
        self.assertNotIn("secret", self.output.read_text())

    def test_inline_declarations_preserve_functions_and_last_property(self):
        self.snapshot("snapshot.json", [frame("1:1", style="width: 30px; width: 48px; background: linear-gradient(180deg, rgba(0,0,0,.2) 0%, #FFFFFF 100%); font-family: 'Noto Sans SC'")])
        data = module.build_inventory(self.manifest([self.source("1:1")]), self.output)
        node = data["nodes"][0]
        self.assertEqual(node["properties"]["width"], "48px")
        self.assertIn("rgba(0,0,0,.2)", node["properties"]["background"])
        self.assertEqual(node["duplicate_properties"], ["width"])

    def test_opaque_paint_and_escaped_resource_functions_do_not_leak_addresses(self):
        values = [
            'image-set("//private.invalid/secret.png" 1x)',
            r'u\72l(https://private.invalid/secret.png)',
            'linear-gradient(#FFF, #000), image-set(private.png 1x)',
        ]
        # Use single-quoted HTML attributes so the CSS image-set quotes remain valid.
        for value in values:
            with self.subTest(value=value):
                code = f"<div data-node-id='1:1' style='background: {value}'></div>"
                self.snapshot("snapshot.json", [code])
                data = module.build_inventory(self.manifest([self.source("1:1")]), self.output, overwrite=True)
                self.assertNotIn("background", data["nodes"][0]["properties"])
                self.assertIn("background:asset-reference", data["nodes"][0]["unknown"])
                encoded = self.output.read_text()
                self.assertNotIn("private", encoded)
                self.assertNotIn("secret.png", encoded)

    def test_missing_root_and_conflicting_manifest_fail_without_writing(self):
        self.snapshot("snapshot.json", [frame("1:1")])
        with self.assertRaisesRegex(ValueError, "absent"):
            module.build_inventory(self.manifest([self.source("1:9")]), self.output)
        self.assertFalse(self.output.exists())
        with self.assertRaisesRegex(ValueError, "Conflicting manifest"):
            module.build_inventory(self.manifest([self.source("1:1"), self.source("1:1", role="prototype")]), self.output)
        self.assertFalse(self.output.exists())

    def test_missing_excluded_root_is_also_rejected(self):
        self.snapshot("snapshot.json", [frame("1:1")])
        with self.assertRaisesRegex(ValueError, "absent"):
            module.build_inventory(self.manifest([self.source("1:9", role="legacy")]), self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_malformed_json_html_and_unknown_roles(self):
        snapshot = self.snapshot("snapshot.json", [frame("1:1")])
        manifest = self.manifest([self.source("1:1", role="designer")])
        with self.assertRaisesRegex(ValueError, "Unknown manifest role"):
            module.build_inventory(manifest, self.output)
        manifest = self.manifest([self.source("1:1")])
        snapshot.write_text('{"content": [], "content": []}')
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            module.build_inventory(manifest, self.output)
        self.snapshot("snapshot.json", ['<div data-node-id="1:1"><span></div>'])
        with self.assertRaisesRegex(ValueError, "nesting"):
            module.build_inventory(manifest, self.output)
        self.assertFalse(self.output.exists())

    def test_refuses_existing_output_and_input_overwrite(self):
        snapshot = self.snapshot("snapshot.json", [frame("1:1")])
        manifest = self.manifest([self.source("1:1")])
        data = module.build_inventory(manifest, self.output)
        original = self.output.read_bytes()
        with self.assertRaises(FileExistsError):
            module.build_inventory(manifest, self.output)
        self.assertEqual(self.output.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "must not replace"):
            module.build_inventory(manifest, snapshot, overwrite=True)
        with self.assertRaisesRegex(ValueError, "must not replace"):
            module.build_inventory(manifest, manifest, overwrite=True)
        self.assertEqual(module.build_inventory(manifest, self.output, overwrite=True), data)

    def test_hardlinked_output_cannot_truncate_an_input(self):
        snapshot = self.snapshot("snapshot.json", [frame("1:1")])
        manifest = self.manifest([self.source("1:1")])
        for source in (snapshot, manifest):
            with self.subTest(source=source.name):
                if self.output.exists():
                    self.output.unlink()
                os.link(source, self.output)
                original = source.read_bytes()
                with self.assertRaisesRegex(ValueError, "must not replace"):
                    module.build_inventory(manifest, self.output, overwrite=True)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(self.output.read_bytes(), original)

    def test_cli_requires_both_paths_and_success_reports_only_counts(self):
        script = ROOT / "scripts/style_inventory.py"
        missing = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        self.snapshot("snapshot.json", [frame("1:1")])
        manifest = self.manifest([self.source("1:1")])
        done = subprocess.run([sys.executable, str(script), "--manifest", str(manifest), "--output", str(self.output)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["measured_nodes"], 1)
        self.assertNotIn("Private", done.stdout)


if __name__ == "__main__":
    unittest.main()
