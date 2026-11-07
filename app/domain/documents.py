from enum import Enum


class DocumentStatus(str, Enum):
    """Lifecycle states shared by documents and their processing tasks."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"

    @property
    def is_terminal(self) -> bool:
        return self in {
            DocumentStatus.COMPLETED,
            DocumentStatus.FAILED,
            DocumentStatus.PENDING_REVIEW,
        }
