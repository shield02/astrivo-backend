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

- Python 3.13
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

## Advanced and principal-level architecture

The following design extends the basic upload-and-extract workflow into a senior/principal-level system for large, unreliable, and sensitive document collections. These are architectural requirements and implementation backlog items; they are not all implemented in the portfolio build.

### Principal engineering pillars

1. **Distributed map-reduce processing for large documents**
   - Split 500+ page documents into bounded semantic sections such as balance sheets, income statements, leases, and risk factors.
   - Dispatch map jobs across ARQ workers and aggregate validated partial results in a reduce job.
   - Resolve cross-page contradictions and preserve the source pages that support the final value.

2. **Idempotency, distributed locking, and exactly-once effects**
   - Hash raw document bytes with SHA-256 before processing.
   - Use tenant-scoped unique constraints and idempotency keys to prevent duplicate document records.
   - Use Redis locks or an equivalent lease to prevent concurrent processing of the same task.
   - Make retries safe even when a worker crashes after an external API call.

3. **Human-in-the-loop review queues**
   - Attach confidence to every extracted financial figure and checkbox.
   - Route values below the calibrated threshold, currently proposed as `0.85`, to `pending_review`.
   - Give reviewers page, bounding-box, and source-text evidence beside the extracted value.
   - Record approvals, corrections, and reprocessing as auditable events.

4. **Adaptive rate limiting and backpressure**
   - Estimate page and token cost before dispatching expensive work.
   - Apply token-bucket limits for Azure OpenAI requests and bounded concurrency for OCR jobs.
   - Respect provider `429` responses with retry-after handling, exponential backoff, and jitter.
   - Stop accepting or defer work when configured tenant or system budgets are exhausted.

5. **Deterministic schema evolution**
   - Version extraction contracts explicitly, for example `DueDiligenceExtractionV1` and `DueDiligenceExtractionV2`.
   - Store the schema version beside every JSONB payload.
   - Keep old payloads readable and provide explicit migrations when fields change.
   - Never silently reinterpret historical extraction data with a newer schema.

6. **Distributed tracing and correlated logging**
   - Propagate a correlation ID from FastAPI through Redis/ARQ, OCR polling, LLM calls, and persistence.
   - Instrument request duration, queue latency, OCR failures, extraction failures, retries, and token consumption.
   - Send traces and metrics to an OpenTelemetry-compatible backend such as Azure Monitor, Jaeger, or Datadog.
   - Keep document contents, prompts, credentials, and sensitive extracted values out of logs.

### OCR and extraction design rationale

The production pipeline deliberately separates perception from reasoning:

```text
raw PDF
  → document classification
  → OCR/layout analysis
  → structured pages, tables, selection marks, and evidence
  → schema-constrained LLM extraction
  → strict Pydantic validation
  → confidence/review decision
```

Azure AI Document Intelligence is the intended perception layer because scanned financial documents require spatial layout, multi-page table reconstruction, and checkbox/selection-mark detection. A basic text-only extractor such as PyPDF2 or pdfplumber cannot reliably handle scanned pages, table geometry, skew, noise, or selection marks. The LLM should reason over the normalized layout output rather than perform all document perception itself.

### Additional production implementation phases

- **Document classification and pre-routing:** inspect the first pages, classify supported types such as `SEC_10K`, `BALANCE_SHEET`, or `AUDIT_REPORT`, and reject or route unknown documents before expensive processing.
- **Automated evaluation and ground-truth harness:** maintain 20–50 hand-verified documents and JSON fixtures; measure extraction accuracy, faithfulness, and schema compliance in regression runs.
- **Dead-letter and poison-message handling:** retry transient failures with backoff; after the retry budget is exhausted, persist a DLQ record, mark the task failed, and alert operators.
- **Database persistence and migrations:** persist documents, tasks, extraction versions, review tasks, and audit events with indexed JSONB metadata. The initial documents/tasks/extractions migrations are implemented; review/audit persistence remains.
- **Frontend and HITL dashboard:** provide upload, status polling, result viewing, source evidence, and side-by-side reviewer correction/sign-off workflows.

### Hardening pillars

1. **Zero-trust security and privacy**
   - JWT authentication, role-based authorization, TLS, managed identities, Key Vault, encrypted storage, retention controls, and verified provider data-handling terms.
   - Roles initially proposed: `Viewer`, `Compliance_Officer`, and `Admin`.
   - Add PII/confidential-data scrubbing only where policy requires it, with explicit review of the risks of altering source evidence.

2. **Resiliency and graceful degradation**
   - Circuit breakers for OCR and LLM providers.
   - Secondary model/region or manual-review fallback where appropriate.
   - Graceful worker shutdown with checkpointing or safe requeue on termination.
   - Redis locks and database uniqueness to prevent duplicate effects.

3. **FinOps and LLM cost governance**
   - Hard page and token caps per document.
   - Per-tenant rate and budget limits.
   - Usage metrics for OCR pages, LLM tokens, retries, and processing duration.
   - Safe caching for identical inputs only when tenant and retention boundaries permit it.

4. **SRE metrics and alerting**
   - Prometheus/OpenTelemetry metrics such as `document_processing_duration_seconds`, `ocr_extraction_failure_total`, `active_background_tasks`, and `llm_token_consumption_total`.
   - Alerts for queue growth, repeated provider failures, DLQ arrivals, latency regressions, and cost anomalies.

5. **Infrastructure scaling and network isolation**
   - KEDA-driven worker scaling based on Redis queue depth.
   - Private endpoints and VNet integration for PostgreSQL, Redis, Blob Storage, and AI services.
   - No public exposure of internal data services in production.

### Ultra-advanced extensions

- **Neo4j Graph RAG and cross-document relationship mapping:** extract entities such as parent companies, subsidiaries, executives, liabilities, properties, and obligations into a graph so users can query relationships across multiple documents.
- **Dynamic compliance policy engine:** allow authorized compliance teams to define safe rules or a restricted DSL that evaluates validated extraction outputs without code deployments.
- **Multimodal vision fallback:** route ambiguous handwritten charts, damaged tables, or difficult page regions to a vision-capable model after ordinary OCR/layout analysis flags them for fallback.

These extensions are optional principal-level capabilities, not part of the initial portfolio baseline. Neo4j is therefore documented as a planned Graph RAG component rather than an installed dependency.

### DevSecOps and delivery layer

- **Infrastructure as Code:** Terraform or Azure Bicep for VNets, Container Apps, PostgreSQL, Redis, Key Vault, storage, AI services, identities, and monitoring.
- **CI/CD:** GitHub Actions or equivalent for tests, Ruff/format checks, dependency checks, container builds, vulnerability scanning with tools such as Trivy, and staged deployment.
- **Local developer experience:** Docker Compose for PostgreSQL and Redis, a local API, a local ARQ worker, deterministic OCR/extraction fixtures, migration commands, and reproducible test data.

### Portfolio hosting on Hetzner

The portfolio deployment can be hosted on a Hetzner Cloud server to demonstrate a real deployed system without maintaining an always-on Azure environment. Hetzner provides cloud servers, Docker images, firewalls, volumes, backups, and snapshots. See the [Hetzner Cloud overview](https://docs.hetzner.com/cloud/servers/overview/) and [Docker image documentation](https://docs.hetzner.com/cloud/apps/list/docker-ce/).

The intended portfolio topology is:

```text
Internet
  → Caddy or Nginx with HTTPS
  → FastAPI container
  → ARQ worker container
  → PostgreSQL container
  → Redis container
```

PostgreSQL and Redis remain on the private Docker network. Only ports `80` and `443` should be publicly exposed. The deployment should use SSH keys, a host firewall, HTTPS, environment-based secret injection, database backups, health checks, and a documented restore process.

For the portfolio deployment:

- Use one Hetzner Cloud server running Docker Compose.
- Use local sample documents rather than confidential customer data.
- Keep deterministic OCR and extraction adapters as the default path.
- Optionally connect to Azure AI Document Intelligence and Azure OpenAI for demonstrations.
- Run Alembic migrations explicitly during deployment.
- Monitor API, worker, Redis, PostgreSQL, disk, and backup health.

Hetzner Cloud is self-managed: server patching, operating-system security, backups, secrets, and application operations remain the project's responsibility. See [Hetzner's security responsibility documentation](https://docs.hetzner.com/general/security-and-identify/technical-and-organizational-measures/). Hosting real client data would require a separate review of data processing terms, residency, encryption, access controls, incident response, and contractual requirements. Azure remains the intended enterprise-hosting option when managed identities, private endpoints, Key Vault, and Azure-native compliance controls are required.

## Portfolio build objective

This project is being built for a portfolio, but the implementation target is production-grade engineering. The portfolio constraint limits ongoing cloud spend and commercial operations; it does not justify weak boundaries, insecure defaults, untested workflows, or toy implementations.

The local build should therefore include production-shaped behavior wherever practical: strict validation, tenant isolation, RLS, migrations, idempotency, retry-safe workers, structured logging, observability hooks, cost limits, deterministic test doubles, and replaceable adapters for Azure services. External services may be mocked or run locally, but their production contracts and failure modes should be represented in code and tests.

## Commercial readiness and customer value

The advanced architecture makes the product technically credible, but technical complexity alone does not make it sellable. Customers are primarily interested in outcomes:

- Faster property and deal screening.
- Fewer missed financial, lease, title, zoning, and environmental risks.
- Reliable extraction of figures with page-level evidence.
- Human review and approval for uncertain results.
- Export to spreadsheets, reports, or existing systems.
- Secure handling of confidential deal documents.
- Integration into the team's existing due-diligence workflow.

The strongest initial product version should focus on one clear workflow:

> Upload a property acquisition package and receive structured financial, lease, title, zoning, environmental, and risk findings with source evidence.

Neo4j, map-reduce processing, tracing, and other advanced components support reliability and scale, but they should not be the primary sales message. The product should be presented as a tool that saves analyst time and reduces missed risks.

Before calling the product commercially ready, it should have:

1. Evaluation results on representative real-estate due-diligence documents.
2. A polished human review and approval workflow.
3. Spreadsheet, report, or API export capabilities.
4. Security and data-handling documentation.
5. At least one pilot with a real-estate developer or similar target customer.
6. Evidence that the system saves meaningful review time or reduces processing cost.

The project can therefore have high portfolio value and strong technical credibility before commercial validation. Paid pilots, customer interviews, accuracy evidence, and measurable workflow improvements are still required before treating it as a proven business.

## Deferred operational and commercial scope

The following items are deferred from ongoing hosted operation or commercial rollout. They are not permission to omit the corresponding architecture, interfaces, security controls, or local test coverage where those can be implemented without paid infrastructure:

1. Always-on Azure deployment.
2. Azure Front Door, WAF, private endpoints, and multi-region infrastructure.
3. AKS or production-scale Azure Container Apps configuration.
4. Real Azure OpenAI and Azure AI Document Intelligence calls as the default processing path.
5. Large-scale cost optimization and token-budget management.
6. Billing, subscriptions, and customer administration.
7. Enterprise SSO and complex role-based access control.
8. Full audit/compliance certification work.
9. High-availability database replication and backup operations.
10. Complex dead-letter queues and distributed workflow orchestration.
11. Load testing at production scale.
12. Multi-document entity graphs and Graph RAG.
13. Advanced reviewer collaboration features.

These are deferred rather than rejected. The code should preserve clean interfaces so they can be added later without replacing the core domain, service, repository, or API layers.

## Local development

Docker Compose currently provides PostgreSQL and Redis for local development. The API and ARQ worker run from the Python environment. Azure integrations are injectable and mockable so ordinary unit and API tests do not require cloud credentials.

### Implementation status — update this section as milestones progress

Milestone 1 — **API and domain foundation: complete**

- `app/main.py` provides the app factory and runnable `app` instance.
- `GET /health` provides the liveness response.
- `app/core/config.py` loads environment-backed settings with safe local defaults.
- `pyproject.toml` defines runtime and development dependencies plus pytest configuration.
- Strict domain and transport schemas are covered by automated tests.

Milestone 2 — **Persistence and tenant boundaries: substantially complete**

- Async SQLAlchemy models and sessions are implemented.
- Alembic migrations create documents, tasks, and extraction tables.
- PostgreSQL RLS is enabled and forced for tenant-owned tables.
- Tenant-scoped repositories and transaction-local tenant context are implemented.
- RLS behavior has been verified against the local PostgreSQL database.

Milestone 3 — **Ingestion and asynchronous processing: partially complete**

- `POST /api/v1/documents/ingest` validates PDF boundaries and creates a queued document record.
- `GET /api/v1/documents/status/{task_id}` returns processing status.
- `GET /api/v1/documents/{document_id}/result` returns persisted extraction results.
- `app/services/` contains ingestion business rules.
- Local file storage and deterministic OCR/extraction adapters are implemented.
- ARQ/Redis queue adapters and an ARQ worker entry point are implemented.
- The processing pipeline persists extraction output and routes low-confidence results to `pending_review`.
- The current test suite has 31 passing tests.

Remaining Milestone 3 work includes live API-to-Redis-to-worker verification, duplicate-upload idempotency, retry/backoff behavior, and dead-letter handling.

The document-processing workflow is now shaped as:

```text
POST /documents/ingest
  → validate PDF and persist metadata
  → enqueue ARQ job in Redis
  → read shared document storage
  → OCR/layout adapter
  → strict structured extraction adapter
  → persist extraction evidence and confidence
  → complete or route to pending_review
```

For the portfolio build, OCR and structured extraction use deterministic local adapters. Set `USE_IN_MEMORY_QUEUE=false` after Redis is running, then start the worker with `make worker`. The local worker uses PostgreSQL and `DOCUMENT_STORAGE_PATH`; Azure adapters can replace the mock OCR and extraction implementations without changing the pipeline boundary.

The backend targets Python 3.13. Create a Python 3.13 virtual environment, install the development dependencies, and run the tests:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The same dependencies are also declared in `pyproject.toml`. The `requirements.txt` file contains runtime dependencies, while `requirements-dev.txt` adds testing and development tools. `.python-version` pins the project to Python 3.13, and VS Code is configured to use `.venv/bin/python`.

The document listing endpoint is not implemented yet. The ingestion endpoint persists to PostgreSQL by default; set `USE_IN_MEMORY_REPOSITORY=true` only for isolated local tests.

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

The Makefile also provides `make db-shell`, `make redis-shell`, `make logs-postgres`, and `make logs-redis`. When buildable services are added, `make build SERVICE=api` builds only the API image, while `make build` builds all images. `make rebuild SERVICE=api` rebuilds and starts only the API service; `make rebuild` rebuilds and starts all Compose services. PostgreSQL is available at `localhost:5432` (database/user `abstrivo`); Redis is available at `localhost:6380` and maps to port `6379` inside the container. The default credentials and port bindings are intended only for local development. Removing Docker volumes deletes the local database/cache data.

