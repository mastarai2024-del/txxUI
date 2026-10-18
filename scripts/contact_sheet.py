#!/usr/bin/env python3
"""Build an indexed contact sheet from local screenshots; never changes inputs."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def build_sheet(paths, output, columns=4, thumb_width=320, overwrite=False):
    """Return an index; writes PNG and JSON only after all inputs decode."""
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
        records.append({
            "number": number,
            "source": str(path),
            "source_size": list(original_size),
            "thumbnail_size": list(tile.size),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

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
        draw.text((x, y + 6), f"{offset + 1:02d}", fill="#222222")
        sheet.paste(tile, (x, y + label_height))
    index = {"output": str(output), "size": [width, height], "images": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG")
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=320)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        result = build_sheet(
            args.images, args.output, args.columns, args.thumb_width, args.overwrite
        )
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        parser.exit(1, f"contact_sheet: {error}\n")
    print(json.dumps({"output": result["output"], "count": len(result["images"])}))


if __name__ == "__main__":
    main()
