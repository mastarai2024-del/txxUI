#!/usr/bin/env python3
"""Resolve a complete Taste v2 installation; install the pinned upstream if absent."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPO = "Leonxlnx/taste-skill"
REVISION = "f624f37a8c650b9cc550253104925efe4c8de246"
SOURCE_PATH = "skills/taste-skill"
INSTALL_NAME = "design-taste-frontend"
LIMIT = 64 * 1024 * 1024
REQUIRED = (
    "SKILL.md", "references/type.md", "references/colour.md",
    "references/layout.md", "references/critique.md", "references/copy.md",
    "references/imagery.md", "references/motion.md", "references/tells.md",
    "references/research.md", "scripts/draw.mjs", "scripts/assets.mjs",
    "scripts/lint.mjs", "scripts/inspect.mjs", "scripts/lib/cdp.mjs",
    "scripts/lib/probe.mjs", "scripts/lib/rules.mjs", "library/directions.json",
    "library/heroes.json", "library/sections.json", "library/type.json",
    "library/palettes.json", "library/photos.json", "library/sites.json",
    "library/motions.json", "assets/base.css", "assets/base.js",
)


class TasteError(Exception):
    pass


def validate(folder: Path) -> None:
    missing = [name for name in REQUIRED if not (folder / name).is_file()]
    if missing:
        raise TasteError("Incomplete Taste installation: " + ", ".join(missing))
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)
    if len(frontmatter) < 3 or not re.search(
        r"(?m)^name:\s*['\"]?design-taste-frontend['\"]?\s*$", frontmatter[1]
    ) or "tasteskill v2" not in text:
        raise TasteError("Expected design-taste-frontend (Taste v2), not another skill")


def default_roots() -> list[Path]:
    home = Path.home()
    codex = Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser()
    return [codex / "skills", home / ".agents" / "skills", home / ".claude" / "skills"]


def find_existing(roots: list[Path]) -> Path | None:
    invalid = []
    for root in roots:
        for name in (INSTALL_NAME, "taste-skill"):
            candidate = root / name
            if not os.path.lexists(candidate):
                continue
            try:
                validate(candidate)
                return candidate.resolve()
            except (OSError, UnicodeError, TasteError) as exc:
                invalid.append(f"{candidate}: {exc}")
    if invalid:
        raise TasteError("Existing Taste needs repair; nothing overwritten. " + "; ".join(invalid))
    return None


def official_installer() -> Path | None:
    codex = default_roots()[0].parent
    path = codex / "skills/.system/skill-installer/scripts/install-skill-from-github.py"
    return path if path.is_file() else None


def download_archive() -> bytes:
    url = f"https://codeload.github.com/{REPO}/zip/{REVISION}"
    request = urllib.request.Request(url, headers={"User-Agent": "txxui-taste-bootstrap"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read(LIMIT + 1)
    if len(payload) > LIMIT:
        raise TasteError("Taste archive exceeds the download limit")
    return payload


def extract_skill(payload: bytes, destination: Path) -> None:
    """Extract only the chosen skill; never execute downloaded code."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        roots = {PurePosixPath(info.filename).parts[0] for info in archive.infolist() if info.filename}
        if len(roots) != 1:
            raise TasteError("Unexpected archive root")
        prefix = next(iter(roots)) + "/" + SOURCE_PATH + "/"
        entries = []
        total = 0
        for info in archive.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            relative = info.filename[len(prefix):]
            parts = PurePosixPath(relative).parts
            if not parts or ".." in parts or ":" in parts[0] or relative.startswith("/") or "\\" in relative:
                raise TasteError("Unsafe archive path")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise TasteError("Archive symlinks are not supported")
            total += info.file_size
            if total > LIMIT:
                raise TasteError("Taste contents exceed the extraction limit")
            entries.append((info, parts))
        if not entries:
            raise TasteError("Taste skill folder not found in archive")
        destination.mkdir()
        for info, parts in entries:
            target = destination.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("xb") as output:
                import shutil
                shutil.copyfileobj(source, output)


def prepare(destination: Path) -> str:
    helper = official_installer()
    if helper:
        completed = subprocess.run(
            [sys.executable, str(helper), "--repo", REPO, "--path", SOURCE_PATH,
             "--ref", REVISION, "--dest", str(destination.parent), "--name", destination.name],
            capture_output=True, text=True, timeout=150,
        )
        if completed.returncode:
            raise TasteError("Official skill-installer failed: " + completed.stderr.strip()[:500])
        return "official-skill-installer"
    extract_skill(download_archive(), destination)
    return "pinned-archive"


def result(path: Path, status: str, method: str | None = None) -> dict:
    value = {"status": status, "skill_dir": str(path.resolve()),
             "skill_file": str((path / "SKILL.md").resolve())}
    if method:
        value.update(method=method, repository=REPO, revision=REVISION)
    return value


def ensure(roots: list[Path], check_only: bool = False) -> dict:
    existing = find_existing(roots)
    if existing:
        return result(existing, "ready")
    if check_only:
        return {"status": "missing", "install_dir": str(roots[0] / INSTALL_NAME)}
    root = roots[0]
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".txxui-taste-install.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise TasteError(f"Taste installation already in progress; inspect {lock}") from exc
    os.close(descriptor)
    try:
        existing = find_existing(roots)
        if existing:
            return result(existing, "ready")
        target = root / INSTALL_NAME
        with tempfile.TemporaryDirectory(prefix=".txxui-taste-", dir=root) as temporary:
            staging = Path(temporary) / INSTALL_NAME
            method = prepare(staging)
            validate(staging)
            (staging / ".txxui-source.json").write_text(
                json.dumps({"repository": REPO, "revision": REVISION, "path": SOURCE_PATH}, indent=2),
                encoding="utf-8",
            )
            if os.path.lexists(target):
                raise TasteError(f"Destination appeared during install; nothing overwritten: {target}")
            staging.rename(target)
        return result(target, "installed", method)
    finally:
        lock.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", type=Path, help="Only search/install under this root (isolated environments)")
    parser.add_argument("--check-only", action="store_true", help="Check without downloading or installing")
    args = parser.parse_args()
    roots = [args.skills_root.expanduser().absolute()] if args.skills_root else default_roots()
    try:
        value = ensure(roots, args.check_only)
    except (TasteError, OSError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
