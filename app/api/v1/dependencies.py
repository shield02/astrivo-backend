from functools import lru_cache
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends
from app.core.config import get_settings
from app.core.database import get_db_session
from app.repositories.documents import (
    DocumentRepository,
    InMemoryDocumentRepository,
    PostgreSQLDocumentRepository,
)
from app.services.ingestion import DocumentIngestionService


@lru_cache
def get_in_memory_document_repository() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


async def get_document_repository() -> AsyncIterator[DocumentRepository]:
    settings = get_settings()
    if settings.use_in_memory_repository:
        yield get_in_memory_document_repository()
        return

    async for session in get_db_session():
        yield PostgreSQLDocumentRepository(session)


def get_current_tenant_id() -> UUID:
    """Temporary local tenant context until authentication is implemented."""

    return UUID(get_settings().local_tenant_id)


def get_ingestion_service(
    repository: DocumentRepository = Depends(get_document_repository),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DocumentIngestionService:
    settings = get_settings()
    return DocumentIngestionService(
        repository=repository,
        max_size_bytes=settings.max_upload_size_bytes,
        tenant_id=tenant_id,
    )
