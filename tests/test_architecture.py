from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.architecture import EDGES, NODES

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_page_renders_diagram_and_nav_tab(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        page = client.get("/architecture")
        home = client.get("/")

    assert page.status_code == 200
    assert "Architecture" in page.text
    assert 'id="arch-data"' in page.text
    for label in ("Trading Journal", "Market Data", "Services layer", "Audit and observability"):
        assert label in page.text
    assert 'href="/architecture"' in home.text


def test_architecture_nodes_are_consistent_with_the_repository():
    ids = {node["id"] for node in NODES}
    assert len(ids) == len(NODES)
    for edge in EDGES:
        assert edge["from"] in ids and edge["to"] in ids
    for node in NODES:
        assert node["summary"]
        for path in node["files"]:
            assert (ROOT / path).exists(), f"{node['id']} references missing path {path}"
