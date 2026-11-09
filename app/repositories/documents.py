from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import set_tenant_context
from app.domain.documents import DocumentStatus
from app.models.documents import DocumentModel, TaskModel


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    document_id: UUID
    task_id: UUID
    tenant_id: UUID
    filename: str
    content_type: str
    content_hash: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime


class DocumentRepository(Protocol):
    async def create_queued(
        self,
        *,
        tenant_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> DocumentRecord: ...

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> DocumentRecord | None: ...


class InMemoryDocumentRepository:
    """Temporary repository used until PostgreSQL persistence is implemented."""

    def __init__(self) -> None:
        self._documents: dict[UUID, DocumentRecord] = {}

    async def create_queued(
        self,
        *,
        tenant_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> DocumentRecord:
        record = DocumentRecord(
            document_id=uuid4(),
            task_id=uuid4(),
            tenant_id=tenant_id,
            filename=filename,
            content_type=content_type,
            content_hash=sha256(content).hexdigest(),
            size_bytes=len(content),
            status=DocumentStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
        )
        self._documents[record.document_id] = record
        return record

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> DocumentRecord | None:
        record = self._documents.get(document_id)
        if record is None or record.tenant_id != tenant_id:
            return None
        return record


class PostgreSQLDocumentRepository:
    """PostgreSQL implementation with explicit tenant scoping and RLS context."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_queued(
        self,
        *,
        tenant_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> DocumentRecord:
        await set_tenant_context(self._session, tenant_id)
        now = datetime.now(timezone.utc)
        document_id = uuid4()
        task_id = uuid4()
        content_hash = sha256(content).hexdigest()
        status = DocumentStatus.QUEUED.value

        self._session.add(
            DocumentModel(
                document_id=document_id,
                tenant_id=tenant_id,
                filename=filename,
                content_type=content_type,
                content_hash=content_hash,
                size_bytes=len(content),
                status=status,
                created_at=now,
            )
        )
        self._session.add(
            TaskModel(
                task_id=task_id,
                document_id=document_id,
                tenant_id=tenant_id,
                status=status,
                created_at=now,
                updated_at=now,
            )
        )
        await self._session.flush()
        return DocumentRecord(
            document_id=document_id,
            task_id=task_id,
            tenant_id=tenant_id,
            filename=filename,
            content_type=content_type,
            content_hash=content_hash,
            size_bytes=len(content),
            status=DocumentStatus.QUEUED,
            created_at=now,
        )

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> DocumentRecord | None:
        await set_tenant_context(self._session, tenant_id)
        model = await self._session.get(DocumentModel, document_id)
        if model is None or model.tenant_id != tenant_id:
            return None
        task = model.task
        if task is None:
            return None
        return DocumentRecord(
            document_id=model.document_id,
            task_id=task.task_id,
            tenant_id=model.tenant_id,
            filename=model.filename,
            content_type=model.content_type,
            content_hash=model.content_hash,
            size_bytes=model.size_bytes,
            status=DocumentStatus(model.status),
            created_at=model.created_at,
        )
