from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1)
    doc_type: str = "note"
    source: str = "manual"
    symbols: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    published_at: str = ""
    enabled: bool = True


class KnowledgeDocumentUpdateRequest(BaseModel):
    title: str | None = None
    doc_type: str | None = None
    source: str | None = None
    symbols: list[str] | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    enabled: bool | None = None
    published_at: str | None = None


class KnowledgeDocumentRead(BaseModel):
    id: int
    title: str
    doc_type: str
    source: str
    summary: str
    symbols: list[str]
    tags: list[str]
    metadata: dict[str, Any]
    status: str
    enabled: bool
    chunk_count: int
    published_at: str
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentRead]


class KnowledgeChunkRead(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    summary: str
    token_count: int
    metadata: dict[str, Any]


class KnowledgeDocumentDetail(KnowledgeDocumentRead):
    content: str
    chunks: list[KnowledgeChunkRead]


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    symbols: list[str] = Field(default_factory=list)
    doc_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=1, le=50)
    require_citations: bool = True


class KnowledgeSearchItem(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    snippet: str
    score: float
    source: str
    doc_type: str
    symbols: list[str]
    tags: list[str]
    citation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    query: str
    items: list[KnowledgeSearchItem]
