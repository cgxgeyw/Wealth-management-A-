from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseRead,
    KnowledgeBaseUpdateRequest,
    KnowledgeChunkRead,
    KnowledgeChunkUpdateRequest,
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentDetail,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentRechunkRequest,
    KnowledgeDocumentRead,
    KnowledgeDocumentUpdateRequest,
    KnowledgeFaissStatus,
    KnowledgeImportTaskListResponse,
    KnowledgeReindexAllResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.knowledge_base import (
    create_knowledge_base,
    create_document,
    create_document_from_file,
    delete_document,
    get_document,
    list_import_tasks,
    list_knowledge_bases,
    list_documents,
    rechunk_document,
    reindex_all_documents,
    reindex_document,
    search_knowledge,
    update_chunk,
    update_knowledge_base,
    update_document,
)
from app.services.knowledge_faiss import faiss_status, rebuild_faiss_index

router = APIRouter()


@router.get("/bases", response_model=KnowledgeBaseListResponse)
def bases(db: Session = Depends(get_db)) -> KnowledgeBaseListResponse:
    return list_knowledge_bases(db)


@router.post("/bases", response_model=KnowledgeBaseRead)
def create_base(
    payload: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeBaseRead:
    return create_knowledge_base(db, payload)


@router.patch("/bases/{base_id}", response_model=KnowledgeBaseRead)
def patch_base(
    base_id: int,
    payload: KnowledgeBaseUpdateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeBaseRead:
    result = update_knowledge_base(db, base_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge base not found.")
    return result


@router.get("/import-tasks", response_model=KnowledgeImportTaskListResponse)
def import_tasks(
    knowledge_base_id: int | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
) -> KnowledgeImportTaskListResponse:
    return list_import_tasks(db, knowledge_base_id=knowledge_base_id, limit=limit)


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
def documents(
    q: str = "",
    limit: int = 50,
    knowledge_base_id: int | None = None,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentListResponse:
    return KnowledgeDocumentListResponse(
        items=list_documents(db, q=q, limit=limit, knowledge_base_id=knowledge_base_id)
    )


@router.post("/documents", response_model=KnowledgeDocumentDetail)
def create_knowledge_document(
    payload: KnowledgeDocumentCreateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentDetail:
    return create_document(db, payload)


@router.post("/documents/upload", response_model=KnowledgeDocumentDetail)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    knowledge_base_id: int = 1,
    chunking_strategy: str = "",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    separators: str = "",
    db: Session = Depends(get_db),
) -> KnowledgeDocumentDetail:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        return create_document_from_file(
            db,
            filename=file.filename or "uploaded-document",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            knowledge_base_id=knowledge_base_id,
            chunking_strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[item.strip() for item in separators.split("|") if item.strip()] if separators else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/reindex-all", response_model=KnowledgeReindexAllResponse)
def reindex_all(db: Session = Depends(get_db)) -> KnowledgeReindexAllResponse:
    return reindex_all_documents(db)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def document_detail(document_id: int, db: Session = Depends(get_db)) -> KnowledgeDocumentDetail:
    result = get_document(db, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return result


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def patch_document(
    document_id: int,
    payload: KnowledgeDocumentUpdateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentDetail:
    result = update_document(db, document_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return result


@router.delete("/documents/{document_id}", response_model=KnowledgeDocumentRead)
def remove_document(document_id: int, db: Session = Depends(get_db)) -> KnowledgeDocumentRead:
    result = get_document(db, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    delete_document(db, document_id)
    return result


@router.post("/documents/{document_id}/reindex", response_model=KnowledgeDocumentDetail)
def reindex(document_id: int, db: Session = Depends(get_db)) -> KnowledgeDocumentDetail:
    result = reindex_document(db, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return result


@router.post("/documents/{document_id}/rechunk", response_model=KnowledgeDocumentDetail)
def rechunk(
    document_id: int,
    payload: KnowledgeDocumentRechunkRequest,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentDetail:
    result = rechunk_document(db, document_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return result


@router.patch("/chunks/{chunk_id}", response_model=KnowledgeChunkRead)
def patch_chunk(
    chunk_id: int,
    payload: KnowledgeChunkUpdateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeChunkRead:
    result = update_chunk(db, chunk_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge chunk not found.")
    return result


@router.post("/search", response_model=KnowledgeSearchResponse)
def search(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> KnowledgeSearchResponse:
    return search_knowledge(db, payload)


@router.get("/faiss/status", response_model=KnowledgeFaissStatus)
def get_faiss_status() -> KnowledgeFaissStatus:
    return faiss_status()


@router.post("/faiss/rebuild", response_model=KnowledgeFaissStatus)
def rebuild_faiss(db: Session = Depends(get_db)) -> KnowledgeFaissStatus:
    return rebuild_faiss_index(db)
