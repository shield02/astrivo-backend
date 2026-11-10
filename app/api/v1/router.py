from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.v1.dependencies import get_current_tenant_id, get_document_repository, get_ingestion_service
from app.api.v1.schemas.documents import DocumentResultResponse, DocumentStatusResponse
from app.api.v1.schemas.ingestion import DocumentIngestResponse
from app.domain.documents import DocumentStatus
from app.repositories.documents import DocumentRepository
from app.services.ingestion import (
    DocumentIngestionService,
    DocumentTooLargeError,
    InvalidDocumentError,
)


# Versioned routes are added here as each milestone is implemented.
router = APIRouter()


@router.post(
    "/documents/ingest",
    response_model=DocumentIngestResponse,
    status_code=202,
    tags=["documents"],
)
async def ingest_document(
    file: UploadFile = File(...),
    service: DocumentIngestionService = Depends(get_ingestion_service),
) -> DocumentIngestResponse | JSONResponse:
    """Accept a validated PDF and create its queued document record."""

    content = await file.read()
    try:
        result = await service.ingest(
            filename=file.filename,
            content_type=file.content_type,
            content=content,
        )
    except DocumentTooLargeError as exc:
        return JSONResponse(status_code=413, content={"detail": str(exc)})
    except InvalidDocumentError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return DocumentIngestResponse(
        document_id=result.document_id,
        task_id=result.task_id,
        status=result.status,
        message=result.message,
    )


@router.get("/documents/status/{task_id}", response_model=DocumentStatusResponse, tags=["documents"])
async def get_document_status(
    task_id: UUID,
    repository: DocumentRepository = Depends(get_document_repository),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DocumentStatusResponse:
    record = await repository.get_by_task(tenant_id=tenant_id, task_id=task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document task was not found.")
    return DocumentStatusResponse(
        task_id=record.task_id,
        document_id=record.document_id,
        status=record.status,
    )


@router.get(
    "/documents/{document_id}/result",
    response_model=DocumentResultResponse,
    tags=["documents"],
)
async def get_document_result(
    document_id: UUID,
    repository: DocumentRepository = Depends(get_document_repository),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DocumentResultResponse:
    record = await repository.get(tenant_id=tenant_id, document_id=document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document was not found.")
    extraction = await repository.get_extraction(
        tenant_id=tenant_id, document_id=document_id
    )
    if extraction is None:
        raise HTTPException(status_code=409, detail="Document extraction is not available.")
    return DocumentResultResponse(
        document_id=document_id,
        status=record.status,
        extraction=extraction.extraction,
    )
