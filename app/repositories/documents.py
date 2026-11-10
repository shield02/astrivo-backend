from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import set_tenant_context
from app.domain.documents import DocumentStatus
from app.models.documents import DocumentModel, ExtractionModel, TaskModel
from app.schemas.extractions import DueDiligenceExtractionV1


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


@dataclass(frozen=True, slots=True)
class ExtractionRecord:
    document_id: UUID
    task_id: UUID
    tenant_id: UUID
    extraction: DueDiligenceExtractionV1


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

    async def get_by_task(self, *, tenant_id: UUID, task_id: UUID) -> DocumentRecord | None: ...

    async def update_status(
        self, *, tenant_id: UUID, document_id: UUID, status: DocumentStatus
    ) -> None: ...

    async def save_extraction(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        task_id: UUID,
        extraction: DueDiligenceExtractionV1,
    ) -> None: ...

    async def get_extraction(
        self, *, tenant_id: UUID, document_id: UUID
    ) -> ExtractionRecord | None: ...


class InMemoryDocumentRepository:
    """Temporary repository used until PostgreSQL persistence is implemented."""

    def __init__(self) -> None:
        self._documents: dict[UUID, DocumentRecord] = {}
        self._extractions: dict[UUID, ExtractionRecord] = {}

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

    async def get_by_task(self, *, tenant_id: UUID, task_id: UUID) -> DocumentRecord | None:
        for record in self._documents.values():
            if record.task_id == task_id and record.tenant_id == tenant_id:
                return record
        return None

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> DocumentRecord | None:
        record = self._documents.get(document_id)
        if record is None or record.tenant_id != tenant_id:
            return None
        return record

    async def update_status(
        self, *, tenant_id: UUID, document_id: UUID, status: DocumentStatus
    ) -> None:
        record = await self.get(tenant_id=tenant_id, document_id=document_id)
        if record is None:
            raise LookupError("Document was not found.")
        self._documents[document_id] = replace(record, status=status)

    async def save_extraction(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        task_id: UUID,
        extraction: DueDiligenceExtractionV1,
    ) -> None:
        if await self.get(tenant_id=tenant_id, document_id=document_id) is None:
            raise LookupError("Document was not found.")
        self._extractions[document_id] = ExtractionRecord(
            document_id=document_id,
            task_id=task_id,
            tenant_id=tenant_id,
            extraction=extraction,
        )

    async def get_extraction(
        self, *, tenant_id: UUID, document_id: UUID
    ) -> ExtractionRecord | None:
        record = self._extractions.get(document_id)
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

    async def get_by_task(self, *, tenant_id: UUID, task_id: UUID) -> DocumentRecord | None:
        await set_tenant_context(self._session, tenant_id)
        from sqlalchemy import select

        result = await self._session.execute(
            select(DocumentModel, TaskModel)
            .join(TaskModel, TaskModel.document_id == DocumentModel.document_id)
            .where(TaskModel.task_id == task_id, TaskModel.tenant_id == tenant_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        document, task = row
        return DocumentRecord(
            document_id=document.document_id,
            task_id=task.task_id,
            tenant_id=document.tenant_id,
            filename=document.filename,
            content_type=document.content_type,
            content_hash=document.content_hash,
            size_bytes=document.size_bytes,
            status=DocumentStatus(document.status),
            created_at=document.created_at,
        )

    async def update_status(
        self, *, tenant_id: UUID, document_id: UUID, status: DocumentStatus
    ) -> None:
        await set_tenant_context(self._session, tenant_id)
        model = await self._session.get(DocumentModel, document_id)
        if model is None or model.tenant_id != tenant_id:
            raise LookupError("Document was not found.")
        model.status = status.value
        if model.task is not None:
            model.task.status = status.value
            model.task.updated_at = datetime.now(timezone.utc)

    async def save_extraction(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        task_id: UUID,
        extraction: DueDiligenceExtractionV1,
    ) -> None:
        await set_tenant_context(self._session, tenant_id)
        self._session.add(
            ExtractionModel(
                extraction_id=uuid4(),
                task_id=task_id,
                document_id=document_id,
                tenant_id=tenant_id,
                schema_version=extraction.schema_version,
                payload=extraction.model_dump(mode="json"),
                created_at=datetime.now(timezone.utc),
            )
        )
        await self._session.flush()

    async def get_extraction(
        self, *, tenant_id: UUID, document_id: UUID
    ) -> ExtractionRecord | None:
        await set_tenant_context(self._session, tenant_id)
        from sqlalchemy import select

        result = await self._session.execute(
            select(ExtractionModel).where(
                ExtractionModel.document_id == document_id,
                ExtractionModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return ExtractionRecord(
            document_id=model.document_id,
            task_id=model.task_id,
            tenant_id=model.tenant_id,
            extraction=DueDiligenceExtractionV1.model_validate(model.payload),
        )
