import asyncio
from pathlib import Path
from typing import Protocol
from uuid import UUID


class DocumentStorage(Protocol):
    async def put(self, *, tenant_id: UUID, document_id: UUID, content: bytes) -> None: ...

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> bytes: ...


class InMemoryDocumentStorage:
    """Local storage adapter for tests and the portfolio demo."""

    def __init__(self) -> None:
        self._objects: dict[tuple[UUID, UUID], bytes] = {}

    async def put(self, *, tenant_id: UUID, document_id: UUID, content: bytes) -> None:
        self._objects[(tenant_id, document_id)] = content

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> bytes:
        try:
            return self._objects[(tenant_id, document_id)]
        except KeyError as exc:
            raise FileNotFoundError("Document content was not found.") from exc


class LocalFileDocumentStorage:
    """Shared local storage adapter for the portfolio worker and API processes."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, tenant_id: UUID, document_id: UUID) -> Path:
        return self._root / str(tenant_id) / f"{document_id}.pdf"

    async def put(self, *, tenant_id: UUID, document_id: UUID, content: bytes) -> None:
        path = self._path(tenant_id, document_id)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)

    async def get(self, *, tenant_id: UUID, document_id: UUID) -> bytes:
        path = self._path(tenant_id, document_id)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise FileNotFoundError("Document content was not found.") from exc
