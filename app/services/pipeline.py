from uuid import UUID

from app.domain.documents import DocumentStatus
from app.repositories.documents import DocumentRepository
from app.services.extraction import StructuredExtraction
from app.services.ocr import DocumentOCR
from app.services.storage import DocumentStorage


class DocumentProcessingService:
    """Runs OCR, structured extraction, validation, and persistence."""

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: DocumentStorage,
        ocr: DocumentOCR,
        extraction: StructuredExtraction,
        review_threshold: float = 0.85,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._ocr = ocr
        self._extraction = extraction
        self._review_threshold = review_threshold

    async def process(
        self, *, tenant_id: UUID, document_id: UUID, task_id: UUID
    ) -> DocumentStatus:
        await self._repository.update_status(
            tenant_id=tenant_id, document_id=document_id, status=DocumentStatus.PROCESSING
        )
        try:
            content = await self._storage.get(tenant_id=tenant_id, document_id=document_id)
            layout = await self._ocr.analyze(
                tenant_id=tenant_id, document_id=document_id, content=content
            )
            extraction = await self._extraction.extract(
                tenant_id=tenant_id, document_id=document_id, layout=layout
            )
            await self._repository.save_extraction(
                tenant_id=tenant_id,
                document_id=document_id,
                task_id=task_id,
                extraction=extraction,
            )
            status = (
                DocumentStatus.PENDING_REVIEW
                if self._requires_review(extraction)
                else DocumentStatus.COMPLETED
            )
            await self._repository.update_status(
                tenant_id=tenant_id, document_id=document_id, status=status
            )
            return status
        except Exception:
            await self._repository.update_status(
                tenant_id=tenant_id, document_id=document_id, status=DocumentStatus.FAILED
            )
            raise

    def _requires_review(self, extraction) -> bool:
        scores = [
            item.confidence_score for item in extraction.financial_figures
        ] + [item.confidence_score for item in extraction.checkboxes]
        return bool(scores) and min(scores) < self._review_threshold
