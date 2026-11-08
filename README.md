# Abstrivo Backend

FastAPI backend for Abstrivo, a document intelligence platform for commercial real estate and financial due diligence. The service accepts documents, extracts structured information, tracks processing, and exposes tenant-scoped results through a versioned API.

> This README describes the intended design and roadmap. Features are plans until implemented and documented as complete.

## Purpose and scope

The backend owns:

- Versioned HTTP APIs and their OpenAPI specification.
- Document ingestion, validation, storage coordination, and processing status.
- Asynchronous OCR and extraction workflows.
- Strictly validated extraction schemas and versioned persistence.
- Authentication, authorization, tenant isolation, and audit-relevant records.
- Background worker operations, retries, and service observability.

The web application belongs in `abstrivo-frontend`; infrastructure as code and deployment pipelines belong in `abstrivo-devops`. Frontend development integrates through this backend's OpenAPI contract and, when available, a staging API. Backend source access is not required for API consumers.

## Initial document workflow

1. A client submits a PDF to `POST /api/v1/documents/ingest` with an authorized tenant context.
2. The API validates the request, calculates a SHA-256 content hash, stores the source document in private object storage, records metadata, and queues processing.
3. The API responds with `202 Accepted` and a task/document identifier; parsing does not block the upload request.
4. ARQ workers use Azure AI Document Intelligence to extract text, layout, tables, and checkbox information. Large documents can be divided into bounded sections for processing.
5. Azure OpenAI produces structured extraction candidates under a versioned Pydantic schema. The backend validates the result, records provenance and confidence, and persists it.
6. Results below the configured confidence threshold are marked `pending_review` for auditor review in the frontend. The backend exposes the review state and relevant evidence through APIs.

The pipeline should preserve source references such as page numbers and spatial locations where available, so users can verify extracted values. Confidence scores support triage; they are not guarantees of correctness.

## Planned architecture

- **HTTP layer:** FastAPI routers, request/response DTOs, authentication dependencies, and API versioning.
- **Domain/services layer:** Ingestion and extraction orchestration, classification, confidence and review decisions.
- **Repositories:** Encapsulated database access, separate from business rules.
- **Persistence:** PostgreSQL with async SQLAlchemy 2.x and Alembic migrations. Structured outputs can use `jsonb` alongside queryable metadata.
- **Tenant isolation:** PostgreSQL Row-Level Security (RLS), with tenant context set within each transaction, for example via `set_config('app.current_tenant_id', ..., true)`. Tenant context must come from authenticated identity, not an untrusted request field.
- **Workers and broker:** ARQ with Redis for durable-enough asynchronous job coordination, retries, and worker scaling. Processing must be idempotent because jobs can be retried.
- **Document storage:** Private Azure Blob Storage for original PDFs and any retained processing artifacts; database records store references and metadata.
- **Document parsing and extraction:** Azure AI Document Intelligence for OCR/layout analysis and Azure OpenAI structured outputs for schema-constrained extraction.

### Extraction quality and review

Schemas should use Pydantic v2 with strict validation and reject unexpected fields where appropriate (`ConfigDict(strict=True, extra="forbid")`). Monetary amounts should use `Decimal`; dates should use `date`; checkbox states should be booleans. Each extraction should identify its schema version and include field-level evidence and confidence where the source services provide it.

The project README proposes a default confidence threshold of `0.85` for routing results to human review. Treat the threshold as configuration to be calibrated against an evaluation dataset, not a universal quality standard. Store extraction versions so corrections and reprocessing remain auditable.

### Reliability, cost, and observability

Planned production controls include bounded uploads and token/page limits, duplicate detection, idempotent job creation, exponential backoff for transient failures, circuit breakers for cloud dependencies, poison-job handling and a dead-letter queue, graceful worker shutdown, and cost-aware rate limiting. Redis caching may be introduced for identical extraction inputs when cache keys and tenant/data boundaries are safe.

Expose health/readiness checks and operational metrics such as processing duration, job outcomes, retry counts, and external-service failures. Logs and traces must avoid leaking document content, credentials, or sensitive extracted values. Alert delivery and hosting configuration are managed with the DevOps repository.

## API surface

Initial API design (subject to implementation and OpenAPI review):

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/v1/documents/ingest` | Upload a PDF and enqueue processing; return `202 Accepted`. |
| `GET` | `/api/v1/documents/status/{task_id}` | Read processing status: queued, processing, completed, failed, or pending review. |
| `GET` | `/api/v1/documents/{document_id}/result` | Retrieve the validated extraction for a completed document. |
| `GET` | `/api/v1/documents` | List documents for the authenticated tenant with pagination and filters. |
| `GET` | `/health` | Liveness/readiness information, designed not to expose sensitive configuration. |

Authorization and tenant scoping apply to every document and task lookup. Avoid exposing whether another tenant's identifiers exist. The generated OpenAPI document is the frontend team's API contract.

## Security and privacy goals

- JWT-based authentication and role-based authorization (initial roles proposed: `Viewer`, `Compliance_Officer`, `Admin`).
- PostgreSQL RLS as a database-level tenant boundary, with tests for cross-tenant isolation.
- TLS in transit, private object storage, and managed encryption at rest.
- Managed identities and a secret manager in deployed Azure environments; no secrets committed to source control.
- Data retention and deletion policies for source PDFs, OCR artifacts, prompts, and results.
- Use Azure service configurations and contractual controls appropriate for sensitive documents. Do not describe zero data retention as guaranteed until the selected service configuration and terms have been verified.

This is a document productivity system. It does not provide investment advice, legal advice, or a guarantee of compliance or extraction accuracy.

## Technology direction

- Python 3.11+
- FastAPI and Pydantic v2
- Async SQLAlchemy 2.x, PostgreSQL, Alembic
- Redis and ARQ
- Azure AI Document Intelligence, Azure OpenAI, and Azure Blob Storage
- pytest and pytest-asyncio for test-driven development
- Docker Compose for local dependencies

Specific dependency versions and service choices will be pinned as implementation begins. Neo4j/Graph RAG is an optional future extension, not part of the initial backend baseline.

## Proposed repository layout

```text
abstrivo-backend/
├── alembic/                  # Database migrations and RLS policies
├── app/
│   ├── api/v1/endpoints/     # Versioned FastAPI endpoints
│   ├── core/                 # Configuration, database, and security
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic API and extraction schemas
│   ├── repositories/         # Data access
│   ├── services/             # Domain and integration orchestration
│   └── workers/              # ARQ jobs
├── tests/                    # Unit, API, and integration tests
├── scripts/                  # Local development and maintenance tools
├── .env.example              # Variable names and safe local defaults only
├── alembic.ini
├── docker-compose.yml        # Local development dependencies
├── Dockerfile
├── main.py
└── pyproject.toml            # Project metadata and tooling (planned)
```

The layout is a starting point and can be adjusted as the code is built. Do not add cloud credentials or real customer documents to the repository.

## Build roadmap

Build incrementally using test-driven development. Each feature should have tests for its behavior and failure cases before it is treated as complete.

### Milestone 1: API and domain foundation

- Establish the Python project, configuration, app factory, and versioned API.
- Define document/task lifecycle states and strict initial extraction schemas.
- Add health endpoint and API contract generation.
- Build tests for schema validation and API request/response behavior.

### Milestone 2: Persistence and tenant boundaries

- Add PostgreSQL models, async sessions, and Alembic migrations.
- Implement tenant identity propagation and RLS policies.
- Verify tenant isolation and migration behavior with integration tests.

### Milestone 3: Ingestion and asynchronous processing

- Validate and accept PDF uploads; persist document metadata and source files.
- Add SHA-256 deduplication and idempotent queue submission.
- Add Redis/ARQ workers, status tracking, retries, and failure handling.
- Test queue behavior without requiring cloud calls.

### Milestone 4: OCR and structured extraction

- Integrate Azure Document Intelligence for layout, text, tables, and checkboxes.
- Classify supported document types and route to the appropriate extraction schema.
- Integrate Azure OpenAI structured output and validate every response.
- Persist evidence, confidence, schema version, and extraction output.
- Add mocked integration tests and a human-verified evaluation dataset before tuning thresholds.

### Milestone 5: Review workflow and production readiness

- Add APIs for review state and auditor corrections, coordinated with the frontend.
- Add DLQ/poison-job handling, rate and cost limits, observability, and operational health checks.
- Add security, load, and end-to-end checks appropriate to deployment readiness.

### Later extensions

- Nightly extraction regression/evaluation harness (LLMOps).
- Vision fallback for low-confidence or difficult page regions.
- Cross-document entity mapping and Graph RAG with Neo4j.
- Configurable compliance policy evaluation.

## Local development

Docker Compose currently provides PostgreSQL and Redis for local development. The API and worker will run from the Python environment once their application scaffold is added. Azure integrations should be injectable and mockable so ordinary unit and API tests do not require cloud credentials.

### Current implementation status

Milestone 1 has started with the FastAPI application foundation:

- `app/main.py` provides the app factory and runnable `app` instance.
- `GET /health` provides the initial liveness response.
- `app/core/config.py` loads environment-backed settings with safe local defaults.
- `pyproject.toml` defines runtime and development dependencies plus pytest configuration.
- `tests/test_health.py` verifies the health response and OpenAPI registration.

Step 2 adds the validated domain and transport contracts:

- `app/domain/` contains business concepts such as document lifecycle states.
- `app/schemas/` contains strict, versioned extraction validation models.
- `app/api/v1/schemas/` contains HTTP response DTOs only; it does not contain query or business logic.
- Repository/query code, services, and response normalization will remain separate as those features are implemented.

Create a Python 3.11+ virtual environment, install the development dependencies, and run the tests:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The same dependencies are also declared in `pyproject.toml`. The `requirements.txt` file contains runtime dependencies, while `requirements-dev.txt` adds testing and development tools. VS Code is configured to use `.venv/bin/python`; use the Python 3.11+ interpreter when creating that environment.

The document endpoints are intentionally not exposed until their request/response behavior is implemented and tested in the next milestones.

```bash
# Optional: copy this file and adjust local ports or database settings.
cp .env.example .env

# See all commands.
make help

# Start dependencies, check status, follow logs, or stop (data is preserved).
make up
make ps
make logs
make down
```

The Makefile also provides `make db-shell`, `make redis-shell`, `make logs-postgres`, and `make logs-redis`. When buildable services are added, `make build SERVICE=api` builds only the API image, while `make build` builds all images. `make rebuild SERVICE=api` rebuilds and starts only the API service; `make rebuild` rebuilds and starts all Compose services. PostgreSQL is available at `localhost:5432` (database/user `abstrivo`); Redis is available at `localhost:6379`. The default credentials and port bindings are intended only for local development. Removing Docker volumes deletes the local database/cache data.

