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


def test_knowledge_faiss_status_endpoint_is_optional() -> None:
    with TestClient(app) as client:
        response = client.get("/api/knowledge/faiss/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] in (True, False)
    assert payload["available"] in (True, False)
    assert payload["model"]
    assert "message" in payload


def test_knowledge_vector_search_can_hydrate_faiss_hits(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[0.5, 0.5] for _ in texts])

    with TestClient(app) as client:
        created = client.post(
            "/api/knowledge/documents",
            json={
                "title": "电网侧储能调研",
                "doc_type": "research",
                "source": "manual",
                "content": "电网侧储能项目招标节奏加快，逆变器和电池系统供应商受益。",
                "symbols": ["300750"],
                "tags": ["储能", "电网"],
            },
        )
        assert created.status_code == 200
        chunk_id = created.json()["chunks"][0]["id"]
        monkeypatch.setattr(
            "app.services.knowledge_base.search_faiss",
            lambda query_vector, top_k: [{"chunk_id": chunk_id, "vector_score": 0.93}],
        )

        searched = client.post(
            "/api/knowledge/search",
            json={"query": "一个只依赖向量召回的查询", "symbols": ["300750"], "top_k": 3},
        )

    assert searched.status_code == 200
    items = searched.json()["items"]
    assert items
    assert items[0]["chunk_id"] == chunk_id
    assert items[0]["title"] == "电网侧储能调研"


def test_knowledge_maintenance_detail_reindex_all_and_delete(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    with TestClient(app) as client:
        created = client.post(
            "/api/knowledge/documents",
            json={
                "title": "交易纪律",
                "doc_type": "strategy",
                "source": "manual",
                "content": "单笔亏损不得超过计划阈值。连续亏损后降低仓位。",
                "symbols": [],
                "tags": ["风控"],
            },
        )
        assert created.status_code == 200
        document_id = created.json()["id"]

        detail = client.get(f"/api/knowledge/documents/{document_id}")
        assert detail.status_code == 200
        assert detail.json()["chunks"]

        reindexed = client.post("/api/knowledge/documents/reindex-all")
        assert reindexed.status_code == 200
        reindex_payload = reindexed.json()
        assert reindex_payload["total"] >= 1
        assert reindex_payload["reindexed"] >= 1
        assert "faiss" in reindex_payload

        deleted = client.delete(f"/api/knowledge/documents/{document_id}")
        assert deleted.status_code == 200
        assert deleted.json()["id"] == document_id

        missing = client.get(f"/api/knowledge/documents/{document_id}")
        assert missing.status_code == 404
