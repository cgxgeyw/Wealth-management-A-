from fastapi.testclient import TestClient

from app.main import app


def test_knowledge_document_create_search_and_tool() -> None:
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
