from dataclasses import dataclass
from uuid import UUID

from app.domain.documents import DocumentStatus
from app.repositories.documents import DocumentRecord, DocumentRepository
from app.services.queue import DocumentTaskQueue, InMemoryDocumentTaskQueue
from app.services.storage import DocumentStorage, InMemoryDocumentStorage


class InvalidDocumentError(ValueError):
    """Raised when an uploaded document fails boundary validation."""


class DocumentTooLargeError(InvalidDocumentError):
    """Raised when an upload exceeds the configured byte limit."""


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: UUID
    task_id: UUID
    status: DocumentStatus
    message: str


class DocumentIngestionService:
    """Coordinates document validation and repository creation."""

    def __init__(
        self,
        repository: DocumentRepository,
        max_size_bytes: int,
        tenant_id: UUID,
        storage: DocumentStorage | None = None,
        queue: DocumentTaskQueue | None = None,
    ) -> None:
        self._repository = repository
        self._max_size_bytes = max_size_bytes
        self._tenant_id = tenant_id
        self._storage = storage or InMemoryDocumentStorage()
        self._queue = queue or InMemoryDocumentTaskQueue()

    async def ingest(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> IngestionResult:
        self._validate_pdf(filename=filename, content_type=content_type, content=content)

        if len(content) > self._max_size_bytes:
            raise DocumentTooLargeError("The uploaded document exceeds the maximum file size.")

        record = await self._repository.create_queued(
            tenant_id=self._tenant_id,
            filename=filename or "document.pdf",
            content_type=content_type or "application/pdf",
            content=content,
        )
        await self._storage.put(
            tenant_id=self._tenant_id,
            document_id=record.document_id,
            content=content,
        )
        await self._queue.enqueue(
            tenant_id=self._tenant_id,
            document_id=record.document_id,
            task_id=record.task_id,
        )
        return self._to_result(record)

    @staticmethod
    def _validate_pdf(
        *,
        filename: str | None,
        content_type: str | None,
        content: bytes,
    ) -> None:
        if not filename or not filename.lower().endswith(".pdf"):
            raise InvalidDocumentError("Only PDF files are supported.")
        if content_type and content_type.lower() != "application/pdf":
            raise InvalidDocumentError("Only PDF files are supported.")
        if not content.startswith(b"%PDF-"):
            raise InvalidDocumentError("The uploaded file is not a valid PDF document.")

    @staticmethod
    def _to_result(record: DocumentRecord) -> IngestionResult:
        return IngestionResult(
            document_id=record.document_id,
            task_id=record.task_id,
            status=record.status,
            message="Document accepted and queued for processing.",
        )
