from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentDetail,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentRead,
    KnowledgeDocumentUpdateRequest,
    KnowledgeFaissStatus,
    KnowledgeReindexAllResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.knowledge_base import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    reindex_all_documents,
    reindex_document,
    search_knowledge,
    update_document,
)
from app.services.knowledge_faiss import faiss_status, rebuild_faiss_index

router = APIRouter()


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
def documents(q: str = "", limit: int = 50, db: Session = Depends(get_db)) -> KnowledgeDocumentListResponse:
    return KnowledgeDocumentListResponse(items=list_documents(db, q=q, limit=limit))


@router.post("/documents", response_model=KnowledgeDocumentDetail)
def create_knowledge_document(
    payload: KnowledgeDocumentCreateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentDetail:
    return create_document(db, payload)


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


@router.post("/search", response_model=KnowledgeSearchResponse)
def search(payload: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> KnowledgeSearchResponse:
    return search_knowledge(db, payload)


@router.get("/faiss/status", response_model=KnowledgeFaissStatus)
def get_faiss_status() -> KnowledgeFaissStatus:
    return faiss_status()


@router.post("/faiss/rebuild", response_model=KnowledgeFaissStatus)
def rebuild_faiss(db: Session = Depends(get_db)) -> KnowledgeFaissStatus:
    return rebuild_faiss_index(db)
