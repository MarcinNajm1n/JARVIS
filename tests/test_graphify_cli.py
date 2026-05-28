from src.graphify_cli import build_local_graph


def test_graphify_buduje_markdown_links_wikilinks_i_tagi(tmp_path):
    (tmp_path / "A.md").write_text(
        "# Start\n[plik B](B.md)\n[[C]]\n#jarvis\n",
        encoding="utf-8",
    )
    (tmp_path / "B.md").write_text("# B\n", encoding="utf-8")
    (tmp_path / "C.md").write_text("# C\n", encoding="utf-8")
    output = tmp_path / "graph.json"

    result = build_local_graph(tmp_path, output)

    assert output.exists()
    node_ids = {node["id"] for node in result.graph["nodes"]}
    edge_types = {edge["type"] for edge in result.graph["edges"]}
    assert "A.md" in node_ids
    assert "B.md" in node_ids
    assert "C.md" in node_ids
    assert "tag:jarvis" in node_ids
    assert {"markdown_link", "wikilink", "tag", "heading"}.issubset(edge_types)
    assert result.graph["mode"] == "graph"


def test_graphify_json_dodaje_klucze_jako_nodes(tmp_path):
    (tmp_path / "data.json").write_text('{"alpha": 1, "beta": 2}', encoding="utf-8")

    result = build_local_graph(tmp_path, tmp_path / "graph.json")

    node_ids = {node["id"] for node in result.graph["nodes"]}
    assert "data.json:alpha" in node_ids
    assert "data.json:beta" in node_ids
