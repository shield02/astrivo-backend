from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.documents import DocumentStatus
from app.schemas.extractions import DueDiligenceExtractionV1


class DocumentStatusResponse(BaseModel):
    """Stable transport shape for document processing status."""

    model_config = ConfigDict(strict=True, extra="forbid")

    task_id: UUID
    document_id: UUID | None = None
    status: DocumentStatus
    error_code: str | None = None


class DocumentResultResponse(BaseModel):
    """Stable transport shape for a validated extraction result."""

    model_config = ConfigDict(strict=True, extra="forbid")

    document_id: UUID
    status: DocumentStatus
    extraction: DueDiligenceExtractionV1
