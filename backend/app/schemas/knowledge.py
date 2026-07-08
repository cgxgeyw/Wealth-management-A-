from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1)
    knowledge_base_id: int = 1
    doc_type: str = "note"
    source: str = "manual"
    symbols: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    published_at: str = ""
    enabled: bool = True
    chunking_strategy: str = "paragraph"
    chunk_size: int = Field(default=900, ge=100, le=8000)
    chunk_overlap: int = Field(default=120, ge=0, le=2000)
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", "。", "；"])


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
    knowledge_base_id: int
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
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    separators: list[str]
    published_at: str
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentRead]


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    chunking_strategy: str = "paragraph"
    chunk_size: int = Field(default=900, ge=100, le=8000)
    chunk_overlap: int = Field(default=120, ge=0, le=2000)
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", "。", "；"])


class KnowledgeBaseRead(BaseModel):
    id: int
    name: str
    description: str
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    separators: list[str]
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseRead]


class KnowledgeChunkRead(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    token_count: int
    metadata: dict[str, Any]


class KnowledgeChunkUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None


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


class KnowledgeFaissStatus(BaseModel):
    enabled: bool
    available: bool
    indexed: bool
    model: str
    dimension: int = 0
    vector_count: int = 0
    index_path: str = ""
    mapping_path: str = ""
    message: str = ""


class KnowledgeReindexAllResponse(BaseModel):
    total: int
    reindexed: int
    failed: int
    faiss: KnowledgeFaissStatus
