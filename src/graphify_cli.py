from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^|\]#]+)(?:#[^|\]]+)?(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".json"}
SKIP_DIRS = {".git", ".venv", "__pycache__", ".cache", "node_modules", "graphify-out"}
DEFAULT_OUTPUT = Path("graphify-out/local_graph.json")


@dataclass(frozen=True)
class GraphifyResult:
    graph: dict[str, Any]
    output_path: Path


class GraphifyParseError(RuntimeError):
    pass


def build_local_graph(input_path: str | Path = ".", output_path: str | Path = DEFAULT_OUTPUT) -> GraphifyResult:
    root = Path(input_path).resolve()
    if not root.exists():
        raise GraphifyParseError(f"Input path does not exist: {root}")
    output = Path(output_path)
    if not output.is_absolute():
        output = Path.cwd() / output
    files = _collect_files(root)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for file_path in files:
        rel = _relative_id(file_path, root)
        nodes[rel] = {
            "id": rel,
            "label": file_path.stem,
            "type": _node_type(file_path),
            "path": rel,
        }
        text = _read_text(file_path)
        if file_path.suffix.lower() in {".md", ".markdown", ".txt"}:
            _add_markdown_edges(rel, text, nodes, edges, root, file_path.parent)
        elif file_path.suffix.lower() == ".json":
            _add_json_edges(rel, text, nodes, edges)

    graph = {
        "type": "visual_result",
        "mode": "graph",
        "presentation": "animated_scene",
        "animation_profile": "result",
        "title": "GRAPH READY",
        "summary": f"{len(nodes)} nodes / {len(edges)} edges",
        "nodes": list(nodes.values()),
        "edges": edges,
        "sources": [str(root)],
        "cost": {"operation": "graphify", "estimated_cost_usd": 0.0},
        "message": f"Graphify built {len(nodes)} nodes and {len(edges)} edges.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    return GraphifyResult(graph=graph, output_path=output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a lightweight JARVIS knowledge graph.")
    parser.add_argument("path", nargs="?", default=".", help="Directory or file to scan.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path. Default: graphify-out/local_graph.json",
    )
    args = parser.parse_args(argv)
    try:
        result = build_local_graph(args.path, args.output)
    except GraphifyParseError as error:
        print(f"GraphifyParseError: {error}")
        return 2
    print(
        f"GRAPH_READY nodes={len(result.graph['nodes'])} "
        f"edges={len(result.graph['edges'])} output={result.output_path}"
    )
    return 0


def _collect_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in SUPPORTED_SUFFIXES else []
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def _add_markdown_edges(
    rel: str,
    text: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    root: Path,
    current_dir: Path,
) -> None:
    for index, heading in enumerate(HEADING_RE.findall(text)):
        level, label = heading
        heading_id = f"{rel}#{_slug(label)}"
        nodes[heading_id] = {
            "id": heading_id,
            "label": label.strip(),
            "type": "heading",
            "path": rel,
            "level": len(level),
        }
        edges.append({"source": rel, "target": heading_id, "type": "heading"})
        if index >= 24:
            break

    for target in MARKDOWN_LINK_RE.findall(text):
        clean = target.split("#", 1)[0].strip()
        if not clean or clean.startswith(("http://", "https://", "mailto:")):
            continue
        target_path = (current_dir / clean).resolve()
        target_id = _relative_id(target_path, root) if _inside(target_path, root) else clean
        nodes.setdefault(target_id, {"id": target_id, "label": Path(target_id).stem, "type": "note", "path": target_id})
        edges.append({"source": rel, "target": target_id, "type": "markdown_link"})

    for target in WIKILINK_RE.findall(text):
        target_id = _resolve_wikilink(target, root)
        nodes.setdefault(target_id, {"id": target_id, "label": target, "type": "note", "path": target_id})
        edges.append({"source": rel, "target": target_id, "type": "wikilink"})

    for tag in TAG_RE.findall(text):
        target_id = f"tag:{tag}"
        nodes.setdefault(target_id, {"id": target_id, "label": f"#{tag}", "type": "tag", "path": ""})
        edges.append({"source": rel, "target": target_id, "type": "tag"})


def _add_json_edges(rel: str, text: str, nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return
    if isinstance(data, dict):
        for key in list(data.keys())[:20]:
            target_id = f"{rel}:{key}"
            nodes[target_id] = {"id": target_id, "label": str(key), "type": "json_key", "path": rel}
            edges.append({"source": rel, "target": target_id, "type": "json_key"})


def _resolve_wikilink(target: str, root: Path) -> str:
    normalized = target.strip()
    for suffix in (".md", ".markdown"):
        candidate = next(root.rglob(f"{normalized}{suffix}"), None)
        if candidate:
            return _relative_id(candidate.resolve(), root)
    return normalized


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig", errors="ignore")


def _relative_id(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _node_type(path: Path) -> str:
    if path.suffix.lower() in {".md", ".markdown"}:
        return "note"
    if path.suffix.lower() == ".json":
        return "json"
    return "text"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-") or "heading"


if __name__ == "__main__":
    raise SystemExit(main())
