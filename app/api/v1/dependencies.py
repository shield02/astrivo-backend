from collections.abc import AsyncIterator
from functools import lru_cache
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis
from fastapi import Depends
from app.core.config import get_settings
from app.core.database import get_db_session
from app.repositories.documents import (
    DocumentRepository,
    InMemoryDocumentRepository,
    PostgreSQLDocumentRepository,
)
from app.services.ingestion import DocumentIngestionService
from app.services.queue import (
    ARQDocumentTaskQueue,
    DocumentTaskQueue,
    InMemoryDocumentTaskQueue,
    redis_settings_from_url,
)
from app.services.storage import DocumentStorage, LocalFileDocumentStorage


@lru_cache
def get_in_memory_document_repository() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


def get_document_storage() -> DocumentStorage:
    return LocalFileDocumentStorage(get_settings().document_storage_path)


@lru_cache
def get_in_memory_task_queue() -> InMemoryDocumentTaskQueue:
    return InMemoryDocumentTaskQueue()


async def get_document_task_queue() -> AsyncIterator[DocumentTaskQueue]:
    settings = get_settings()
    if settings.use_in_memory_queue:
        yield get_in_memory_task_queue()
        return

    redis: ArqRedis = await create_pool(redis_settings_from_url(settings.redis_url))
    try:
        yield ARQDocumentTaskQueue(redis)
    finally:
        await redis.close()


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
    storage: DocumentStorage = Depends(get_document_storage),
    queue: DocumentTaskQueue = Depends(get_document_task_queue),
) -> DocumentIngestionService:
    settings = get_settings()
    return DocumentIngestionService(
        repository=repository,
        max_size_bytes=settings.max_upload_size_bytes,
        tenant_id=tenant_id,
        storage=storage,
        queue=queue,
    )
