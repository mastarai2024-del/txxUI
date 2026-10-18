import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "scripts/ensure_taste.py"
SPEC = importlib.util.spec_from_file_location("ensure_taste", MODULE)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def complete_skill(path):
    for name in bootstrap.REQUIRED:
        file = path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("fixture", encoding="utf-8")
    (path / "SKILL.md").write_text(
        "---\nname: design-taste-frontend\ndescription: Fixture\n---\n# tasteskill v2\n",
        encoding="utf-8",
    )


def archive_bytes(source, extra=None):
    output = io.BytesIO()
    prefix = "taste-pinned/skills/taste-skill/"
    with zipfile.ZipFile(output, "w") as z:
        for path in source.rglob("*"):
            if path.is_file():
                z.writestr(prefix + path.relative_to(source).as_posix(), path.read_bytes())
        if extra:
            z.writestr(prefix + extra, "outside")
        z.writestr("taste-pinned/skills/another-skill/SKILL.md", "not selected")
    return output.getvalue()


class EnsureTasteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_complete_alias_reused_without_network_or_writes(self):
        skill = self.root / "shared/taste-skill"
        complete_skill(skill)
        before = {p.relative_to(skill): p.read_bytes() for p in skill.rglob("*") if p.is_file()}
        with patch.object(bootstrap, "prepare", side_effect=AssertionError("download called")):
            answer = bootstrap.ensure([self.root / "codex", skill.parent])
        self.assertEqual(answer["status"], "ready")
        self.assertEqual(Path(answer["skill_file"]), (skill / "SKILL.md").resolve())
        self.assertFalse((self.root / "codex").exists())
        self.assertEqual(before, {p.relative_to(skill): p.read_bytes() for p in skill.rglob("*") if p.is_file()})

    def test_check_only_has_no_install_side_effect(self):
        missing = self.root / "missing"
        self.assertEqual(bootstrap.ensure([missing], True)["status"], "missing")
        self.assertFalse(missing.exists())

    def test_missing_dependency_installs_complete_skill_and_is_idempotent(self):
        source = self.root / "source"
        complete_skill(source)
        payload = archive_bytes(source)
        target_root = self.root / "skills"
        with patch.object(bootstrap, "official_installer", return_value=None), patch.object(
            bootstrap, "download_archive", return_value=payload
        ) as download:
            first = bootstrap.ensure([target_root])
            second = bootstrap.ensure([target_root])
        self.assertEqual(first["status"], "installed")
        self.assertEqual(second["status"], "ready")
        self.assertEqual(download.call_count, 1)
        target = Path(first["skill_dir"])
        bootstrap.validate(target)
        self.assertEqual(json.loads((target / ".txxui-source.json").read_text())["revision"], bootstrap.REVISION)
        self.assertFalse((target_root / "another-skill").exists())
        self.assertFalse((target_root / ".txxui-taste-install.lock").exists())

    def test_existing_partial_skill_is_never_overwritten(self):
        path = self.root / "skills" / bootstrap.INSTALL_NAME
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text("user-owned partial content")
        with patch.object(bootstrap, "prepare") as prepare, self.assertRaises(bootstrap.TasteError):
            bootstrap.ensure([path.parent])
        prepare.assert_not_called()
        self.assertEqual((path / "SKILL.md").read_text(), "user-owned partial content")

    def test_failed_install_leaves_no_partial_target_and_no_retry(self):
        root = self.root / "skills"
        with patch.object(bootstrap, "official_installer", return_value=None), patch.object(
            bootstrap, "download_archive", side_effect=OSError("offline")
        ) as download, self.assertRaises(OSError):
            bootstrap.ensure([root])
        self.assertEqual(download.call_count, 1)
        self.assertEqual(list(root.iterdir()), [])

    def test_invalid_download_is_not_promoted(self):
        source = self.root / "source"
        complete_skill(source)
        (source / "scripts/inspect.mjs").unlink()
        with patch.object(bootstrap, "official_installer", return_value=None), patch.object(
            bootstrap, "download_archive", return_value=archive_bytes(source)
        ), self.assertRaises(bootstrap.TasteError):
            bootstrap.ensure([self.root / "skills"])
        self.assertEqual(list((self.root / "skills").iterdir()), [])

    def test_archive_cannot_escape_selected_skill(self):
        source = self.root / "source"
        complete_skill(source)
        with self.assertRaises(bootstrap.TasteError):
            bootstrap.extract_skill(archive_bytes(source, "../../outside.txt"), self.root / "destination")
        self.assertFalse((self.root / "outside.txt").exists())
        self.assertFalse((self.root / "destination").exists())

    def test_other_version_with_similar_folder_name_is_rejected(self):
        source = self.root / "taste-skill"
        complete_skill(source)
        (source / "SKILL.md").write_text("---\nname: design-taste-frontend-v1\n---\n# tasteskill v2\n")
        with self.assertRaises(bootstrap.TasteError):
            bootstrap.find_existing([self.root])

    def test_existing_lock_is_preserved(self):
        root = self.root / "skills"
        root.mkdir()
        lock = root / ".txxui-taste-install.lock"
        lock.write_text("another install")
        with self.assertRaises(bootstrap.TasteError):
            bootstrap.ensure([root])
        self.assertEqual(lock.read_text(), "another install")


if __name__ == "__main__":
    unittest.main()
