from uuid import UUID

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import get_engine, get_session_factory
from app.repositories.documents import PostgreSQLDocumentRepository
from app.services.extraction import MockStructuredExtraction
from app.services.ocr import MockDocumentOCR
from app.services.pipeline import DocumentProcessingService
from app.services.storage import LocalFileDocumentStorage


async def process_document(ctx: dict, tenant_id: str, document_id: str, task_id: str) -> None:
    """ARQ job entry point; dependencies are supplied by worker startup."""

    tenant_uuid = UUID(tenant_id)
    async with ctx["session_factory"]() as session:
        pipeline = DocumentProcessingService(
            repository=PostgreSQLDocumentRepository(session),
            storage=ctx["storage"],
            ocr=MockDocumentOCR(),
            extraction=MockStructuredExtraction(),
        )
        try:
            await pipeline.process(
                tenant_id=tenant_uuid,
                document_id=UUID(document_id),
                task_id=UUID(task_id),
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def startup(ctx: dict) -> None:
    settings = get_settings()
    ctx["session_factory"] = get_session_factory()
    ctx["storage"] = LocalFileDocumentStorage(settings.document_storage_path)


async def shutdown(ctx: dict) -> None:
    await get_engine().dispose()


class WorkerSettings:
    functions = [process_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    max_tries = 3
    job_timeout = 15 * 60
