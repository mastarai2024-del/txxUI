#!/usr/bin/env python3
"""Build an indexed screenshot sheet or before/after pairs; never changes inputs."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def build_sheet(paths, output, columns=4, thumb_width=320, overwrite=False):
    """Return an index; writes PNG and JSON only after all inputs decode."""
    return _build_sheet(paths, output, columns, thumb_width, overwrite)


def _build_sheet(paths, output, columns, thumb_width, overwrite, pairs=None):
    output = Path(output).resolve()
    index_path = output.with_suffix(".json")
    sources = [Path(p).resolve() for p in paths]
    if not sources:
        raise ValueError("Provide at least one screenshot.")
    if not 1 <= columns <= 12 or not 1 <= thumb_width <= 4096:
        raise ValueError("columns must be 1..12; thumb-width must be 1..4096.")
    if output.suffix.lower() != ".png":
        raise ValueError("Output must be a .png file.")
    if output in sources or index_path in sources:
        raise ValueError("Output must not replace an input.")
    if not overwrite and (output.exists() or index_path.exists()):
        raise FileExistsError("Output or index already exists; use --overwrite.")

    tiles, records = [], []
    for number, path in enumerate(sources, 1):
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGBA")
            original_size = image.size
            width = min(thumb_width, image.width)
            height = max(1, round(image.height * width / image.width))
            image = image.resize((width, height), Image.Resampling.LANCZOS)
            tile = Image.new("RGB", image.size, "white")
            tile.paste(image, mask=image.getchannel("A"))
            tiles.append(tile)
        record = {
            "number": number,
            "source": str(path),
            "source_size": list(original_size),
            "thumbnail_size": list(tile.size),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if pairs is not None:
            record.update({
                "pair": (number + 1) // 2,
                "role": "before" if number % 2 else "after",
            })
        records.append(record)

    columns = min(columns, len(tiles))
    gap, label_height = 12, 28
    cell_width = max(tile.width for tile in tiles)
    cell_height = max(tile.height for tile in tiles)
    rows = math.ceil(len(tiles) / columns)
    width = gap + columns * (cell_width + gap)
    height = gap + rows * (cell_height + label_height + gap)
    if width * height > 40_000_000:
        raise ValueError("Sheet exceeds 40 MP; split inputs or reduce thumb-width.")

    sheet = Image.new("RGB", (width, height), "#E8E8E8")
    draw = ImageDraw.Draw(sheet)
    for offset, tile in enumerate(tiles):
        x = gap + (offset % columns) * (cell_width + gap)
        y = gap + (offset // columns) * (cell_height + label_height + gap)
        label = f"{offset + 1:02d}"
        if pairs is not None:
            role = "BEFORE" if offset % 2 == 0 else "AFTER"
            label = f"{offset // 2 + 1:02d} {role}"
        draw.text((x, y + 6), label, fill="#222222")
        sheet.paste(tile, (x, y + label_height))
    index = {"output": str(output), "size": [width, height], "images": records}
    if pairs is not None:
        index.update({"mode": "pairs", "pairs": pairs})
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG")
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


def build_pairs(pairs, output, thumb_width=320, overwrite=False):
    """Pair explicit states without guessing names or normalizing unequal images."""
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Provide a nonempty pairs list.")
    sources, records, states = [], [], set()
    for number, pair in enumerate(pairs, 1):
        if not isinstance(pair, dict):
            raise ValueError("Each pair must be an object.")
        state = pair.get("state")
        if not isinstance(state, str) or not state.strip():
            raise ValueError("Each pair needs a nonempty state.")
        state = state.strip()
        if state in states:
            raise ValueError("Pair states must be unique.")
        states.add(state)
        paths = []
        for role in ("before", "after"):
            value = pair.get(role)
            if not isinstance(value, (str, Path)) or not str(value).strip():
                raise ValueError(f"Pair {number} needs a {role} screenshot path.")
            paths.append(Path(value).resolve())
        before, after = paths
        if before == after:
            raise ValueError("Before and after must use different source files.")
        changes = pair.get("changes", [])
        if not isinstance(changes, list) or any(not isinstance(x, str) for x in changes):
            raise ValueError("Pair changes must be a list of text descriptions.")
        with Image.open(before) as image:
            before_size = ImageOps.exif_transpose(image).size
        with Image.open(after) as image:
            after_size = ImageOps.exif_transpose(image).size
        if before_size != after_size:
            raise ValueError(
                f"Pair {number} dimensions differ: {before_size} vs {after_size}. "
                "Check the state and export scale; do not stretch sources."
            )
        sources.extend(paths)
        records.append({
            "number": number, "state": state,
            "before": str(before), "after": str(after),
            "changes": list(changes),
        })
    return _build_sheet(sources, output, 2, thumb_width, overwrite, pairs=records)


def read_pairs_manifest(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("pairs"), list):
        raise ValueError("Manifest must contain a pairs list.")
    pairs = []
    for pair in data["pairs"]:
        if not isinstance(pair, dict):
            raise ValueError("Each pair must be an object.")
        resolved = dict(pair)
        for role in ("before", "after"):
            value = pair.get(role)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Each pair needs a {role} screenshot path.")
            resolved[role] = (path.parent / value).resolve()
        pairs.append(resolved)
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="*", type=Path)
    parser.add_argument("--pairs", type=Path, help="JSON manifest; pairs use two columns.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=320)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if bool(args.images) == bool(args.pairs):
        parser.error("Provide screenshot paths or --pairs, exclusively.")
    try:
        if args.pairs:
            output = args.output.resolve()
            if args.pairs.resolve() in (output, output.with_suffix(".json")):
                raise ValueError("Output must not replace the pairs manifest.")
            result = build_pairs(
                read_pairs_manifest(args.pairs), output, args.thumb_width, args.overwrite
            )
        else:
            result = build_sheet(
                args.images, args.output, args.columns, args.thumb_width, args.overwrite
            )
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        parser.exit(1, f"contact_sheet: {error}\n")
    summary = {"output": result["output"], "count": len(result["images"])}
    if "pairs" in result:
        summary["pairs"] = len(result["pairs"])
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
