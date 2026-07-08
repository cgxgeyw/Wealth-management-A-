from fastapi.testclient import TestClient

from app.main import app


def test_knowledge_document_create_search_and_tool(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    with TestClient(app) as client:
        created = client.post(
            "/api/knowledge/documents",
            json={
                "title": "宁德时代储能业务笔记",
                "doc_type": "note",
                "source": "manual",
                "content": "宁德时代储能系统出货增长。海外大客户订单是主要驱动。\n\n毛利率改善来自原材料成本下降。",
                "symbols": ["300750"],
                "tags": ["储能", "宁德时代"],
            },
        )
        assert created.status_code == 200
        document = created.json()
        assert document["chunk_count"] >= 1

        listed = client.get("/api/knowledge/documents?q=储能")
        assert listed.status_code == 200
        assert any(item["id"] == document["id"] for item in listed.json()["items"])

        searched = client.post(
            "/api/knowledge/search",
            json={"query": "储能业务增长驱动", "symbols": ["300750"], "top_k": 5},
        )
        assert searched.status_code == 200
        items = searched.json()["items"]
        assert items
        assert items[0]["citation"].startswith("doc:")
        assert items[0]["symbols"] == ["300750"]

        client.patch(
            "/api/agents/research_director",
            json={"tools": ["knowledge.search"], "change_note": "enable knowledge search"},
        )
        tool_response = client.post(
            "/api/agent-tools/research_director/knowledge.search/run",
            json={"params": {"query": "储能业务增长驱动", "symbols": ["300750"], "top_k": 3}},
        )

    assert tool_response.status_code == 200
    assert tool_response.json()["output"]["items"]


def test_knowledge_vector_search_uses_embedding_path(monkeypatch) -> None:
    def fake_embed_texts(texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            if "储能" in text or "海外" in text:
                vectors.append([1.0, 0.0, 0.0])
            else:
                vectors.append([0.0, 1.0, 0.0])
        return vectors

    monkeypatch.setattr("app.services.knowledge_base.embed_texts", fake_embed_texts)

    with TestClient(app) as client:
        created = client.post(
            "/api/knowledge/documents",
            json={
                "title": "海外储能订单纪要",
                "doc_type": "note",
                "source": "manual",
                "content": "海外大客户订单推动储能系统出货增长。",
                "symbols": ["300750"],
                "tags": ["储能"],
            },
        )
        assert created.status_code == 200

        searched = client.post(
            "/api/knowledge/search",
            json={"query": "海外储能", "symbols": ["300750"], "top_k": 3},
        )

    assert searched.status_code == 200
    items = searched.json()["items"]
    assert items
    assert items[0]["title"] == "海外储能订单纪要"
