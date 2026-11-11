from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LayoutPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class LayoutDocument:
    pages: tuple[LayoutPage, ...]

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)


class DocumentOCR(Protocol):
    async def analyze(
        self, *, tenant_id: UUID, document_id: UUID, content: bytes
    ) -> LayoutDocument: ...


class MockDocumentOCR:
    """Deterministic OCR substitute for local development and tests."""

    async def analyze(
        self, *, tenant_id: UUID, document_id: UUID, content: bytes
    ) -> LayoutDocument:
        text = content.decode("utf-8", errors="replace")
        return LayoutDocument(pages=(LayoutPage(page_number=1, text=text),))
