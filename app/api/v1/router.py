from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.api.v1.dependencies import get_ingestion_service
from app.api.v1.schemas.ingestion import DocumentIngestResponse
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
