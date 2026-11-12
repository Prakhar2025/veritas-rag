"""Request and response schemas per the API contract (docs/07)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestDocument(BaseModel):
    """One uploaded PDF with its access tags."""

    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1)
    departments: list[str] = Field(default_factory=lambda: ["general"])


class IngestRequest(BaseModel):
    """Ingest one or more PDF documents."""

    documents: list[IngestDocument] = Field(min_length=1)


class IngestItemResult(BaseModel):
    """Per document ingestion outcome."""

    filename: str
    status: str  # indexed | unchanged | failed
    chunks: int = 0
    reason: str = ""


class IngestResponse(BaseModel):
    """Ingestion summary with the new index version."""

    results: list[IngestItemResult]
    index_version: int


class ChatRequest(BaseModel):
    """One conversation turn."""

    session_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2000)
    role: str = "analyst"
    stream: bool = True


class CitationModel(BaseModel):
    """A resolved citation."""

    n: int
    doc: str
    page: int
    section: str


class ChatResponse(BaseModel):
    """Non streaming chat answer."""

    answer: str
    citations: list[CitationModel]
    meta: dict[str, object]
