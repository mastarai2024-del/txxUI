#!/usr/bin/env python3
"""Inventory explicit MasterGo styles from a local, curated source manifest.

This reads only the manifest and its named JSON snapshots. It does not fetch
assets, calculate browser styles, or decide which observed value is a standard.
"""

import argparse
from collections import defaultdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re


ROLES = {"designer-final", "spec", "ai-comparison", "prototype", "legacy", "uncertain"}
INCLUDED_ROLES = {"designer-final", "spec"}
NODE_ID = re.compile(r"^\d+:\d+$")
PROPERTIES = frozenset({
    "font-family", "font-size", "line-height", "font-weight", "font-style",
    "letter-spacing", "color", "background", "background-color", "opacity",
    "border", "border-width", "border-color", "border-style", "border-radius",
    "border-top-left-radius", "border-top-right-radius", "border-bottom-left-radius",
    "border-bottom-right-radius", "box-shadow", "width", "height", "min-width",
    "max-width", "min-height", "max-height", "padding", "padding-left",
    "padding-right", "padding-top", "padding-bottom", "gap", "row-gap",
    "column-gap", "text-align", "display", "flex-direction", "align-items",
    "justify-content", "position", "left", "right", "top", "bottom",
    "transform", "transform-origin", "object-fit", "overflow", "mix-blend-mode",
})
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
WARNINGS = [
    "Only explicitly exported inline properties are measured; missing properties are unknown, not zero or inherited values.",
    "SVG/image geometry, component internals, computed styles, font availability and visual correctness are not inferred or fetched.",
    "Occurrences describe samples, not design standards. Independent families follow the curated manifest and require human source/role review.",
    "Source-role overlap is checked within a snapshot and byte-identical copies. Node IDs from independently exported snapshots require human document-provenance review.",
]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON contains duplicate keys.")
        result[key] = value
    return result


def _decode_json(raw, name):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid UTF-8 JSON: {name}") from error


def _read_json(path):
    return _decode_json(path.read_bytes(), path.name)


def _opaque_value(key, value):
    # Escapes and resource functions are deliberately opaque. This is a small
    # inventory filter, not a CSS parser or a resource resolver.
    if "\\" in value or re.search(
        r"(?:url|(?:-webkit-)?image-set|image|cross-fade)\s*\(|(?:https?|data|file|asset|generated-images):|//",
        value, re.I,
    ):
        return True
    if key in {"background", "background-color", "color", "border-color"}:
        if not re.fullmatch(r"[a-zA-Z0-9#%,.\s()+-]+", value):
            return True
        functions = re.findall(r"([a-zA-Z-]+)\s*\(", value)
        allowed = {"rgb", "rgba", "hsl", "hsla", "linear-gradient", "radial-gradient",
                   "conic-gradient", "repeating-linear-gradient", "repeating-radial-gradient",
                   "repeating-conic-gradient"}
        if any(function.lower() not in allowed for function in functions):
            return True
    return False


def _declarations(style):
    """Split inline CSS without breaking quoted or parenthesized semicolons."""
    parts, current, quote, depth, escaped = [], [], None, 0, False
    for character in style:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if character == "\\":
            current.append(character)
            escaped = True
            continue
        if quote:
            current.append(character)
            if character == quote:
                quote = None
        elif character in "\"'":
            current.append(character)
            quote = character
        elif character == "(":
            current.append(character)
            depth += 1
        elif character == ")":
            current.append(character)
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced inline CSS.")
        elif character == ";" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    if quote or depth:
        raise ValueError("Unbalanced inline CSS.")
    parts.append("".join(current))
    properties, duplicates, asset_properties = {}, set(), set()
    for part in parts:
        if not part.strip():
            continue
        key, separator, value = part.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not separator or not key or not value:
            raise ValueError("Malformed inline CSS declaration.")
        if key not in PROPERTIES:
            continue
        if key in properties or key in asset_properties:
            duplicates.add(key)
        # Never leak asset addresses embedded in otherwise measurable properties.
        # The final declaration still wins, including an opaque final value.
        if _opaque_value(key, value):
            properties.pop(key, None)
            asset_properties.add(key)
        else:
            asset_properties.discard(key)
            properties[key] = value
    return properties, sorted(duplicates), sorted(asset_properties)


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.roots = []

    def _open(self, tag, attrs, closed=False):
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            raise ValueError("Duplicate HTML attributes.")
        node_id = attributes.get("data-node-id")
        if "data-node-id" in attributes and (not isinstance(node_id, str) or not NODE_ID.fullmatch(node_id)):
            raise ValueError("Invalid exported node ID.")
        if any(key in attributes and not isinstance(attributes[key], str) for key in ("style", "src")):
            raise ValueError("Exported style/src attributes need explicit string values.")
        properties, duplicates, assets = _declarations(attributes.get("style", ""))
        missing = [f"{key}:not-explicit" for key in ("width", "height") if key not in properties]
        source = attributes.get("src", "").lower().split("?", 1)[0].split("#", 1)[0]
        if tag == "svg" or (tag == "img" and (source.endswith(".svg") or source.startswith("data:image/svg"))):
            missing.append("svg-geometry:not-inspected")
        elif tag == "img":
            missing.append("image-content:not-inspected")
        if tag == "ui-component":
            missing.append("component-internals:not-inspected")
        missing.extend(f"{key}:asset-reference" for key in assets)
        node = {
            "tag": tag, "node_id": node_id, "properties": properties,
            "unknown": missing, "duplicate_properties": duplicates, "children": [],
        }
        if self.stack:
            self.stack[-1]["children"].append(node)
        else:
            self.roots.append(node)
        if tag not in VOID_TAGS and not closed:
            self.stack.append(node)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, closed=True)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if not self.stack or self.stack[-1]["tag"] != tag:
            raise ValueError("Malformed exported HTML nesting.")
        self.stack.pop()


def _parse_html(code):
    parser = _Tree()
    parser.feed(code)
    parser.close()
    if parser.stack or len(parser.roots) != 1:
        raise ValueError("Each exported code block must have one complete root.")
    root = parser.roots[0]
    if root["node_id"] is None:
        raise ValueError("Exported root has no node ID.")
    return root


def _snapshot_roots(data):
    if not isinstance(data, dict) or data.get("isError") is True:
        raise ValueError("Snapshot must be a successful MCP result object.")
    content = data.get("content")
    if not isinstance(content, list) or not content:
        raise ValueError("Snapshot content must be a nonempty list.")
    blocks = []
    fence = chr(96) * 3
    for item in content:
        if not isinstance(item, dict):
            raise ValueError("Invalid MCP content item.")
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            raise ValueError("MCP text content must be a string.")
        fenced = re.findall(fence + r"html\s*\n(.*?)\n" + fence, text, re.S | re.I)
        if fenced:
            blocks.extend(fenced)
        elif "代码内容：" in text:
            blocks.append(text.split("代码内容：", 1)[1].strip())
    if not blocks:
        raise ValueError("Snapshot contains no recognized exported HTML.")
    roots = {}
    for block in blocks:
        root = _parse_html(block)
        previous = roots.get(root["node_id"])
        if previous is not None and previous != root:
            raise ValueError(f"Conflicting exports for root {root['node_id']}.")
        roots[root["node_id"]] = root
    return roots


def _manifest_sources(data, base):
    if not isinstance(data, dict) or set(data) != {"sources"}:
        raise ValueError("Manifest must contain only a sources list.")
    if not isinstance(data["sources"], list) or not data["sources"]:
        raise ValueError("Manifest sources must be a nonempty list.")
    records, seen = [], {}
    for entry in data["sources"]:
        if not isinstance(entry, dict) or set(entry) != {"snapshot", "root_id", "family", "role"}:
            raise ValueError("Each source needs snapshot, root_id, family and role.")
        if any(not isinstance(value, str) or not value.strip() for value in entry.values()):
            raise ValueError("Source fields must be nonempty strings.")
        if not NODE_ID.fullmatch(entry["root_id"]):
            raise ValueError("Invalid manifest root_id.")
        if entry["role"] not in ROLES:
            raise ValueError("Unknown manifest role.")
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", entry["snapshot"]):
            raise ValueError("Snapshots must be explicitly named local files.")
        snapshot = (base / entry["snapshot"]).resolve()
        key = (snapshot, entry["root_id"])
        value = (entry["family"], entry["role"])
        if key in seen:
            if seen[key] != value:
                raise ValueError(f"Conflicting manifest entries for root {entry['root_id']}.")
            continue
        seen[key] = value
        records.append({**entry, "snapshot": snapshot})
    return records


def _check_role_overlap(sources, cache):
    """Reject contradictory subtree roles before any measurements or writes."""
    groups = defaultdict(lambda: {"included": set(), "excluded": set()})

    def node_ids(node):
        result = {node["node_id"]} if node["node_id"] else set()
        for child in node["children"]:
            result.update(node_ids(child))
        return result

    for source in sources:
        roots, digest = cache[source["snapshot"]]
        bucket = "included" if source["role"] in INCLUDED_ROLES else "excluded"
        groups[digest][bucket].update(node_ids(roots[source["root_id"]]))
    for group in groups.values():
        overlap = group["included"] & group["excluded"]
        if overlap:
            raise ValueError(
                f"Included and excluded source subtrees overlap at node {sorted(overlap)[0]}; "
                "split or reclassify sources before inventory."
            )


def build_inventory(manifest, output, overwrite=False):
    """Validate every input before writing; return a text/asset-free inventory."""
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    if output.suffix.lower() != ".json":
        raise ValueError("Output must be a .json file.")
    sources = _manifest_sources(_read_json(manifest), manifest.parent)
    inputs = {manifest, *(source["snapshot"] for source in sources)}
    if output in inputs or (output.exists() and any(
        path.exists() and output.samefile(path) for path in inputs
    )):
        raise ValueError("Output must not replace the manifest or a snapshot.")
    if output.exists() and not overwrite:
        raise FileExistsError("Output already exists; use --overwrite.")

    cache, records, nodes, seen_nodes = {}, [], [], {}
    for source in sources:
        path, root_id = source["snapshot"], source["root_id"]
        if path not in cache:
            raw = path.read_bytes()
            cache[path] = (_snapshot_roots(_decode_json(raw, path.name)), hashlib.sha256(raw).hexdigest())
        roots, digest = cache[path]
        if root_id not in roots:
            raise ValueError(f"Manifest root {root_id} is absent from its snapshot.")
    _check_role_overlap(sources, cache)

    statistics = defaultdict(lambda: {"occurrences": 0, "families": set()})
    for source in sources:
        path, root_id = source["snapshot"], source["root_id"]
        roots, digest = cache[path]
        included = source["role"] in INCLUDED_ROLES
        record = {
            "root_id": root_id, "family": source["family"], "role": source["role"],
            "snapshot_sha256": digest, "status": "included" if included else "excluded",
            "node_count": 0,
        }
        records.append(record)
        if not included:
            continue

        def visit(node, trail):
            # Anonymous nodes are scoped to their named root and structural path.
            identity = (path, node["node_id"] or (root_id, trail))
            context = (source["role"], source["family"])
            if identity in seen_nodes:
                previous_context, previous_node = seen_nodes[identity]
                if previous_context != context:
                    raise ValueError("Overlapping source nodes have conflicting role/family assignments.")
                if previous_node != node:
                    raise ValueError("Overlapping source nodes have conflicting exported properties.")
                return
            else:
                seen_nodes[identity] = (context, node)
                measured = {
                    "node_id": node["node_id"], "root_id": root_id, "path": trail,
                    "tag": node["tag"], "family": source["family"], "role": source["role"],
                    "properties": node["properties"], "unknown": node["unknown"],
                }
                if node["duplicate_properties"]:
                    measured["duplicate_properties"] = node["duplicate_properties"]
                nodes.append(measured)
                record["node_count"] += 1
                for property_name, value in node["properties"].items():
                    stats = statistics[(source["role"], property_name, value)]
                    stats["occurrences"] += 1
                    stats["families"].add(source["family"])
            for index, child in enumerate(node["children"]):
                visit(child, f"{trail}/{index}")

        visit(roots[root_id], "0")

    summary = [{
        "role": role, "property": property_name, "value": value,
        "occurrences": stats["occurrences"],
        "independent_families": len(stats["families"]),
        "families": sorted(stats["families"]),
    } for (role, property_name, value), stats in sorted(statistics.items())]
    result = {
        "schema_version": 1, "sources": records, "nodes": nodes, "summary": summary,
        "counts": {"included_roots": sum(x["status"] == "included" for x in records),
                   "excluded_roots": sum(x["status"] == "excluded" for x in records),
                   "measured_nodes": len(nodes)},
        "warnings": WARNINGS,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects against a concurrent writer after validation.
    with output.open("w" if overwrite else "x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        result = build_inventory(args.manifest, args.output, args.overwrite)
    except (OSError, ValueError) as error:
        parser.exit(1, f"style_inventory: {error}\n")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
