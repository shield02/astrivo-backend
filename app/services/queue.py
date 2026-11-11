from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from arq import ArqRedis
from arq.connections import RedisSettings


class DocumentTaskQueue(Protocol):
    async def enqueue(self, *, tenant_id: UUID, document_id: UUID, task_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class QueuedDocumentJob:
    tenant_id: UUID
    document_id: UUID
    task_id: UUID


class InMemoryDocumentTaskQueue:
    def __init__(self) -> None:
        self.jobs: list[QueuedDocumentJob] = []

    async def enqueue(self, *, tenant_id: UUID, document_id: UUID, task_id: UUID) -> None:
        self.jobs.append(QueuedDocumentJob(tenant_id, document_id, task_id))


class ARQDocumentTaskQueue:
    """Redis/ARQ adapter; the worker owns processing and retry configuration."""

    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue(self, *, tenant_id: UUID, document_id: UUID, task_id: UUID) -> None:
        await self._redis.enqueue_job(
            "process_document",
            str(tenant_id),
            str(document_id),
            str(task_id),
            _job_id=str(task_id),
        )


def redis_settings_from_url(redis_url: str) -> RedisSettings:
    return RedisSettings.from_dsn(redis_url)
