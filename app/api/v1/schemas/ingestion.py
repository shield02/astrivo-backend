from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.documents import DocumentStatus


class DocumentIngestResponse(BaseModel):
    """Response returned after a document passes ingestion validation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    document_id: UUID
    task_id: UUID
    status: DocumentStatus
    message: str
