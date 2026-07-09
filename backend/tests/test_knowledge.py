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


def test_knowledge_document_upload_extracts_file_content(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    with TestClient(app) as client:
        uploaded = client.post(
            "/api/knowledge/documents/upload",
            files={
                "file": (
                    "储能行业调研.md",
                    "# 储能行业调研\n\n电网侧储能招标增加，PCS 和电池系统需求改善。",
                    "text/markdown",
                )
            },
        )

    assert uploaded.status_code == 200
    document = uploaded.json()
    assert document["title"] == "储能行业调研"
    assert document["doc_type"] == "markdown"
    assert document["source"] == "upload:储能行业调研.md"
    assert document["chunk_count"] >= 1
    assert "电网侧储能" in document["content"]
    assert document["metadata"]["filename"] == "储能行业调研.md"
    assert document["metadata"]["import_task_id"]

    with TestClient(app) as client:
        tasks = client.get("/api/knowledge/import-tasks")

    assert tasks.status_code == 200
    task_items = tasks.json()["items"]
    assert task_items
    latest = task_items[0]
    assert latest["filename"] == "储能行业调研.md"
    assert latest["document_id"] == document["id"]
    assert latest["status"] == "completed"
    assert latest["stage"] == "completed"
    assert latest["chunk_count"] == document["chunk_count"]


def test_knowledge_bases_upload_chunking_and_edit_chunks(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    with TestClient(app) as client:
        bases = client.get("/api/knowledge/bases")
        assert bases.status_code == 200
        assert any(item["name"] == "默认知识库" for item in bases.json()["items"])

        created_base = client.post(
            "/api/knowledge/bases",
            json={
                "name": "研报知识库",
                "description": "券商研报和行业调研",
                "chunking_strategy": "characters",
                "chunk_size": 120,
                "chunk_overlap": 10,
                "separators": ["\n\n", "。"],
            },
        )
        assert created_base.status_code == 200
        base = created_base.json()
        assert base["name"] == "研报知识库"
        assert base["chunking_strategy"] == "characters"

        content = "新能源车销量改善。" * 20 + "\n\n储能招标节奏加快。" * 15
        uploaded = client.post(
            f"/api/knowledge/documents/upload?knowledge_base_id={base['id']}&chunking_strategy=characters&chunk_size=120&chunk_overlap=10",
            files={
                "file": (
                    "新能源行业周报.txt",
                    content,
                    "text/plain; charset=utf-8",
                )
            },
        )
        assert uploaded.status_code == 200
        document = uploaded.json()
        assert document["knowledge_base_id"] == base["id"]
        assert document["chunking_strategy"] == "characters"
        assert document["chunk_size"] == 120
        assert document["chunk_count"] > 1
        assert document["chunks"][0]["tags"]

        listed = client.get(f"/api/knowledge/documents?knowledge_base_id={base['id']}")
        assert listed.status_code == 200
        assert any(item["id"] == document["id"] for item in listed.json()["items"])

        chunk_id = document["chunks"][0]["id"]
        updated = client.patch(
            f"/api/knowledge/chunks/{chunk_id}",
            json={"content": "编辑后的分块正文，重点关注储能和新能源车。", "tags": ["储能", "新能源车"]},
        )
        assert updated.status_code == 200
        chunk = updated.json()
        assert "编辑后的分块正文" in chunk["content"]
        assert chunk["tags"] == ["储能", "新能源车"]


def test_knowledge_upload_failure_records_import_task(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    with TestClient(app) as client:
        failed = client.post(
            "/api/knowledge/documents/upload",
            files={
                "file": (
                    "空白资料.txt",
                    "   ",
                    "text/plain; charset=utf-8",
                )
            },
        )
        assert failed.status_code == 400

        tasks = client.get("/api/knowledge/import-tasks")
        assert tasks.status_code == 200
        latest = tasks.json()["items"][0]
        assert latest["filename"] == "空白资料.txt"
        assert latest["status"] == "failed"
        assert latest["stage"] == "failed"
        assert latest["document_id"] == 0
        assert "extractable text" in latest["message"]


def test_knowledge_async_import_task_completes(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    with TestClient(app) as client:
        queued = client.post(
            "/api/knowledge/documents/import?chunking_strategy=characters&chunk_size=120&chunk_overlap=5",
            files={
                "file": (
                    "异步导入测试.md",
                    "异步导入会先创建任务，然后后台解析、分块、索引。" * 8,
                    "text/markdown",
                )
            },
        )
        assert queued.status_code == 200
        task = queued.json()
        assert task["filename"] == "异步导入测试.md"
        assert task["status"] in ("queued", "processing", "completed")

        detail = client.get(f"/api/knowledge/import-tasks/{task['id']}")
        assert detail.status_code == 200
        completed = detail.json()
        assert completed["status"] == "completed"
        assert completed["stage"] == "completed"
        assert completed["document_id"] > 0
        assert completed["chunk_count"] >= 1

        document = client.get(f"/api/knowledge/documents/{completed['document_id']}")
        assert document.status_code == 200
        assert document.json()["metadata"]["import_task_id"] == task["id"]


def test_knowledge_base_update_and_document_rechunk(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_base.embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])

    with TestClient(app) as client:
        created_base = client.post(
            "/api/knowledge/bases",
            json={
                "name": "公告知识库",
                "chunking_strategy": "paragraph",
                "chunk_size": 300,
                "chunk_overlap": 0,
            },
        )
        assert created_base.status_code == 200
        base = created_base.json()

        updated_base = client.patch(
            f"/api/knowledge/bases/{base['id']}",
            json={
                "chunking_strategy": "separators",
                "chunk_size": 100,
                "chunk_overlap": 8,
                "separators": ["。"],
            },
        )
        assert updated_base.status_code == 200
        assert updated_base.json()["chunking_strategy"] == "separators"
        assert updated_base.json()["chunk_size"] == 100
        assert updated_base.json()["separators"] == ["。"]

        created_document = client.post(
            "/api/knowledge/documents",
            json={
                "knowledge_base_id": base["id"],
                "title": "公司公告摘要",
                "doc_type": "announcement",
                "source": "manual",
                "content": "第一段公告内容较长。" * 10 + "\n\n第二段包含经营情况。" * 10,
                "chunking_strategy": "paragraph",
                "chunk_size": 500,
                "chunk_overlap": 0,
            },
        )
        assert created_document.status_code == 200
        document = created_document.json()
        original_chunk_count = document["chunk_count"]

        rechunked = client.post(
            f"/api/knowledge/documents/{document['id']}/rechunk",
            json={
                "chunking_strategy": "characters",
                "chunk_size": 100,
                "chunk_overlap": 5,
                "separators": ["。"],
            },
        )
        assert rechunked.status_code == 200
        payload = rechunked.json()
        assert payload["chunking_strategy"] == "characters"
        assert payload["chunk_size"] == 100
        assert payload["chunk_overlap"] == 5
        assert payload["chunk_count"] >= original_chunk_count


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
