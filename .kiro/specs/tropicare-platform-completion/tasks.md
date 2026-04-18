# Implementation Plan: TropiCare Platform Completion

## Overview

This plan implements the TropiCare platform completion across 35 requirements in dependency order. Foundation work (restructuring, migrations, schemas) comes first, followed by core agent intelligence, authentication, security, observability, frontend improvements, resilience, and testing. Each task references specific requirements and builds incrementally on prior steps.

## Tasks

- [x] 1. Backend restructuring and dead code removal
  - [x] 1.1 Extract agents from monolithic base.py into separate module files
    - Extract `IntakeAgent` from `backend/app/agents/base.py` into `backend/app/agents/intake.py`
    - Extract `DiagnosticAgent` into `backend/app/agents/diagnostic.py`
    - Extract `AntibiotherapyAgent` into `backend/app/agents/antibiotherapy.py`
    - Extract `ValidationAgent` into `backend/app/agents/validation.py`
    - Retain only `BaseAgent`, `AgentSpan`, and `MCPClient` in `backend/app/agents/base.py`
    - Update `backend/app/agents/__init__.py` to re-export all agents from new module paths
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Remove stub and duplicate files
    - Delete `backend/app/agents/diagnostic_agent.py`, `backend/app/agents/treatment_agent.py`, `backend/app/agents/resistance_agent.py`, `backend/app/agents/orchestrator.py`
    - Delete `backend/app/api/routes.py` and `backend/app/api/__init__.py`
    - Delete `backend/app/rag/retriever.py`, `backend/app/rag/__init__.py`, `backend/app/rag/ingest.py`
    - _Requirements: 1.3, 2.1, 2.2_

  - [x] 1.3 Create consolidated settings and fix import bugs
    - Delete the old ChromaDB-based `backend/app/config/settings.py` and replace it with a new consolidated `backend/app/config/settings.py` with all env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `MONGODB_URI`, `MONGODB_DB`, `MCP_URL`, `MODEL`, `CORS_ORIGINS`, `JWT_PUBLIC_KEY_PATH`
    - Fix missing `import os` in `backend/app/gateway/auth.py`
    - Fix `from typing import list` → `from typing import List` (or use built-in `list`) in `backend/app/gateway/config.py`
    - Update all backend imports to reference new module paths
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 2.7, 1.4_

- [x] 2. Consolidate Pydantic models and schemas
  - [x] 2.1 Rewrite backend/app/models/schemas.py with all domain models
    - Define `LabResult`, `Medication`, `VitalSigns`, `Symptom`, `PatientContext`, `ConfirmatoryTest`, `DiagnosisItem`, `EmergencyFlag`, `DiagnosticDifferential`, `DrugRegimen`, `Contraindication`, `TreatmentPlan`, `AMRProfile`, `DDIWarning`, `ConsultationResponse`, `AnalyticsSummary` as specified in the design
    - Ensure `PatientContext` fields match the frontend `IntakeForm` component exactly
    - Add `Field(ge=0.0, le=1.0)` constraint on `DiagnosisItem.confidence`
    - Add mandatory `disclaimer` field on `TreatmentPlan`
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 2.2 Update agent implementations to import from consolidated schemas
    - Replace all inline dict usage in agents with Pydantic model imports from `backend/app/models/schemas.py`
    - _Requirements: 3.2_

  - [x] 2.3 Write property test for PatientContext round-trip (Property 1)
    - **Property 1: PatientContext serialization round-trip**
    - Use Hypothesis `@given` with `builds(PatientContext)` to generate arbitrary valid PatientContext objects
    - Verify `PatientContext.model_validate_json(ctx.model_dump_json()) == ctx`
    - Place in `tests/property/test_patient_context_roundtrip.py`
    - **Validates: Requirements 3.3, 17.4**

- [x] 3. Checkpoint — Ensure restructuring is clean
  - Ensure all imports resolve, no circular dependencies, ask the user if questions arise.

- [x] 4. Set up test directory structure and configuration
  - [x] 4.1 Set up test directory structure and pytest configuration
    - Create `tests/unit/agents/`, `tests/unit/tools/`, `tests/integration/api/`, `tests/integration/orchestrator/`, `tests/property/`
    - Create `frontend/__tests__/components/`, `frontend/__tests__/hooks/`
    - Create `pyproject.toml` with pytest configuration, test discovery paths, and markers for unit, integration, and property tests
    - Create `tests/conftest.py` with shared fixtures
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 5. MongoDB Atlas Vector Search migration
  - [x] 5.1 Create backend/app/tools/db.py with MongoDB, PostgreSQL, and Redis singletons
    - Implement `get_mongo_db()` using `motor.AsyncIOMotorClient` with `maxPoolSize=20`, `minPoolSize=2`, `serverSelectionTimeoutMS=5000`
    - Retain existing `get_postgres_pool()` and `get_redis()` singletons
    - _Requirements: 35.2_

  - [x] 5.2 Migrate MCP tools server from Qdrant to MongoDB Atlas Vector Search
    - Replace all Qdrant imports and calls in `backend/app/tools/server.py` with MongoDB `$vectorSearch` aggregation pipeline
    - Define Atlas Vector Search index on `kb_vectors` collection: 3072 dimensions, cosine similarity, filter fields for `disease_tags`, `content_type`, `language`, `superseded`
    - Update `vector_search` tool to use `$vectorSearch` pipeline stage
    - Remove `_qdrant()` singleton and all `qdrant_client` imports
    - _Requirements: 35.1, 35.3, 35.7_

  - [x] 5.3 Migrate ingestion pipeline from Qdrant to MongoDB
    - Update `backend/app/ingestion/store.py` to use `motor` MongoDB client instead of `AsyncQdrantClient`
    - Update `backend/app/ingestion/pipeline.py` to pass `mongo_db` instead of `qdrant` client
    - Update `backend/app/ingestion/worker.py` to initialize MongoDB client instead of Qdrant
    - _Requirements: 35.4_

  - [x] 5.4 Update docker-compose.yml for MongoDB
    - Remove `qdrant` service, `qdrant-init` service, and `qdrant_data` volume
    - Remove `QDRANT_URL` and `QDRANT_COLLECTION` from `x-common-env`
    - Add `MONGODB_URI` and `MONGODB_DB` to `x-common-env`
    - Add MongoDB 7 service with replica set configuration for local development
    - Add `mongo-init` service to run `rs.initiate()` on first startup
    - _Requirements: 35.5, 35.6_

- [x] 6. Frontend type and file consolidation
  - [x] 6.1 Consolidate TypeScript types and remove legacy files
    - Merge `frontend/src/types/index.ts` and `frontend/src/lib/types.ts` into single `frontend/src/lib/types.ts` with all domain types from design
    - Remove duplicate `frontend/src/globals.css`, retain only `frontend/src/app/globals.css`
    - Remove legacy `frontend/src/components/ResultsPanel.tsx` and `frontend/src/components/SymptomForm.tsx`
    - Update all frontend imports to reference consolidated type file
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 6.2 Fix chat/page.tsx type mismatch
    - Change `handleIntakeComplete` parameter type from `Record<string, unknown>` to `PatientContext`
    - Import `PatientContext` from `@/lib/types`
    - _Requirements: 27.3_

- [x] 7. Checkpoint — Ensure restructuring and migration compile cleanly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Authentication and authorization
  - [x] 8.1 Implement user registration endpoint
    - Create `POST /api/v1/auth/register` in `backend/app/gateway/routers/auth.py`
    - Hash passwords with bcrypt (cost factor ≥ 12)
    - Validate password: ≥10 chars, 1 uppercase, 1 lowercase, 1 digit
    - Return HTTP 409 for duplicate email, HTTP 422 for weak password
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 8.2 Implement login with JWT RS256 and refresh tokens
    - Create `POST /api/v1/auth/login` returning access token (8h expiry) and refresh token (30d expiry)
    - Create `POST /api/v1/auth/refresh` for token rotation
    - Sign tokens with RS256 using private key
    - Return HTTP 401 for invalid credentials, HTTP 423 for locked accounts
    - Implement account lockout after 5 failed attempts within 30 minutes (15-minute lock)
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

  - [x] 8.3 Implement RBAC enforcement
    - Enforce "admin" role on document management and analytics endpoints
    - Enforce "clinician" role on session creation, turn submission, and feedback endpoints
    - Return HTTP 403 when role is absent
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [x] 8.4 Write property test for password validation (Property 8)
    - **Property 8: Password validation rejects weak passwords**
    - Use Hypothesis to generate strings missing required character classes
    - Verify registration rejects each with validation error
    - Place in `tests/property/test_password_validation.py`
    - **Validates: Requirement 13.3**

- [x] 9. Security hardening
  - [x] 9.1 Implement security headers middleware
    - Create `backend/app/gateway/middleware.py` with Starlette middleware
    - Set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security: max-age=31536000`, `Content-Security-Policy: default-src 'self'` on every response
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

  - [x] 9.2 Implement input validation and CSRF protection
    - Add `max_length=5000` constraint on all request body string fields via Pydantic models
    - Add region enum validation: `Maritime`, `Plateaux`, `Centrale`, `Kara`, `Savanes`
    - Add email regex validation on registration
    - Implement CSRF double-submit cookie pattern for state-changing endpoints
    - Configure rate limiting: 30/min sessions, 60/min turns, 10/min auth
    - _Requirements: 23.1, 23.2, 23.3, 23.5, 23.6_

  - [x] 9.3 Implement PII hashing in audit logger
    - Enhance `AuditLogger.log()` to SHA-256 hash `age_years`, `weight_kg`, `chief_complaint`, symptom `text` entries, and `allergies` before writing to `audit_log`
    - _Requirements: 23.4_

  - [x] 9.4 Write property test for security headers (Property 10)
    - **Property 10: Security headers on every response**
    - Use Hypothesis to generate random valid HTTP requests (various methods, paths)
    - Verify all responses contain required security headers
    - Place in `tests/property/test_security_headers.py`
    - **Validates: Requirements 22.1, 22.2, 22.3, 22.4**

  - [x] 9.5 Write property test for PII hashing (Property 11)
    - **Property 11: PII hashing in audit logs**
    - Use Hypothesis to generate random audit payloads with PII fields
    - Verify SHA-256 hashing is applied before persistence
    - Place in `tests/property/test_audit_pii_hashing.py`
    - **Validates: Requirement 23.2**

- [x] 10. Checkpoint — Auth and security verified
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Agent intelligence — Diagnostic Agent
  - [x] 11.1 Implement full DiagnosticAgent with ReAct loop and MCP tool calls
    - Ensure `DiagnosticAgent._execute` invokes `hybrid_retrieve` with ≥2 query expansions (symptom-based and epidemiological)
    - Invoke `epid_calendar` MCP tool with patient region and current month
    - Implement ReAct loop with up to 4 iterations, detecting `RETRIEVE:` signals
    - Return 3–5 ranked diagnoses with ICD-11 codes, confidence [0.0, 1.0], supporting evidence with chunk IDs, confirmatory tests with Togo availability
    - Emit `emergency_flag` events for meningitis, severe malaria, viral hemorrhagic fever, septic shock before diagnostic content
    - Retry LLM call once on invalid JSON output before returning structured error
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 8.1_

  - [x] 11.2 Write property test for diagnostic output structural invariants (Property 2)
    - **Property 2: Diagnostic output structural invariants**
    - Generate random `DiagnosticDifferential` objects, verify field constraints (non-empty disease_name, icd11_code, confidence in [0.0, 1.0], ≥1 supporting_evidence, valid availability_togo values)
    - Place in `tests/property/test_diagnostic_invariants.py`
    - **Validates: Requirements 7.1, 7.2, 7.3, 17.6**

  - [x] 11.3 Write property test for diagnostic parser correctness (Property 9)
    - **Property 9: Diagnostic output parser correctness**
    - Generate random strings (valid JSON, invalid JSON, partial JSON)
    - Verify parser produces valid `DiagnosticDifferential` or raises `ValueError` — never silently produces malformed output
    - Place in `tests/property/test_diagnostic_invariants.py`
    - **Validates: Requirement 17.5**

- [x] 12. Agent intelligence — Treatment and Resistance Agents
  - [x] 12.1 Implement full AntibiotherapyAgent with MCP tool integration
    - Invoke `hybrid_retrieve` with ≥3 query expansions (PNLP protocol, antibiotherapy guidelines, WHO posology)
    - Invoke `formulary_lookup` for CAME availability, `amr_lookup` to deprioritize drugs with >30% resistance
    - Calculate mg/kg dosage for pediatric patients, include route/frequency/duration
    - Invoke `safety_classifier` for pregnant patients, include only FDA A/B/C drugs
    - Invoke `drug_ddi_check` and emit severity-tagged interaction warnings
    - Append mandatory regulatory disclaimer to every treatment plan
    - _Requirements: 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 10.4_

  - [x] 12.2 Implement Resistance Agent logic within AntibiotherapyAgent
    - Invoke `amr_lookup` for resistance profiles matching inferred pathogens and patient region
    - Fall back to "West Africa" region when no Togo-specific data exists, indicating fallback source
    - Include resistance percentage, confidence level, data source, and year for each pair
    - Return structured response indicating data unavailability when no AMR data exists, recommending empirical PNLP protocol
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 12.3 Write property test for treatment disclaimer invariant (Property 4)
    - **Property 4: Treatment disclaimer invariant**
    - Generate random `TreatmentPlan` objects via `AntibiotherapyAgent._parse_output`
    - Verify disclaimer field is present and starts with "⚠️ AIDE À LA DÉCISION UNIQUEMENT"
    - Place in `tests/property/test_treatment_invariants.py`
    - **Validates: Requirements 10.4, 17.7**

  - [x] 12.4 Write property test for high-resistance drug exclusion (Property 6)
    - **Property 6: High-resistance drug exclusion from first-line**
    - Generate random treatment plans with AMR data indicating >30% resistance
    - Verify those drugs do not appear in `first_line`
    - Place in `tests/property/test_treatment_invariants.py`
    - **Validates: Requirement 9.3**

  - [x] 12.5 Write property test for pregnancy safety filtering (Property 7)
    - **Property 7: Pregnancy safety filtering**
    - Generate random treatment plans for pregnant patients
    - Verify all drugs in first_line/second_line/alternatives have pregnancy_class A, B, or C
    - Place in `tests/property/test_treatment_invariants.py`
    - **Validates: Requirement 10.2**

- [x] 13. Orchestrator clinical alerts, references, and validation
  - [x] 13.1 Implement Orchestrator warning generation and reference collection
    - Generate clinical warning messages from emergency flags in diagnostic result
    - Add high-resistance warnings when AMR data indicates >30% resistance for recommended drugs
    - Add DDI warnings for "contraindicated" or "major" severity interactions with drug names and management
    - Collect and deduplicate all references into `ConsultationResponse.references` with source attribution (OMS, PNLP, MSF)
    - Wire `ValidationAgent.run_validation` for both diagnostic and antibiotherapy outputs
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 8.2_

  - [x] 13.2 Write property test for emergency flag ordering (Property 3)
    - **Property 3: Emergency flag ordering invariant**
    - Generate random lists of SSE events including `emergency_flag` and `differential_item`
    - Pass through Orchestrator ordering logic, verify all emergency_flag events precede all differential_item events
    - Place in `tests/property/test_event_ordering.py`
    - **Validates: Requirements 7.4, 17.8**

  - [x] 13.3 Write property test for citation deduplication (Property 5)
    - **Property 5: Citation deduplication invariant**
    - Generate random citation lists with duplicates, pass through deduplication logic
    - Verify uniqueness by (source_title, section) tuple
    - Place in `tests/property/test_treatment_invariants.py`
    - **Validates: Requirements 12.4, 17.9**

- [x] 14. Checkpoint — Agent pipeline end-to-end verified
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Observability stack
  - [x] 15.1 Implement OpenTelemetry tracing
    - Configure `opentelemetry-sdk` + `opentelemetry-exporter-otlp` to export traces to Jaeger (:4317)
    - Create child spans for each agent execution with attributes: agent name, latency_ms, input_tokens, output_tokens, verdict
    - Create spans for MCP tool invocations with tool name and result count
    - _Requirements: 24.1, 24.2, 24.3_

  - [x] 15.2 Implement Prometheus metrics and structured logging
    - Mount `prometheus_client.make_asgi_app()` at `/metrics`
    - Add request count counter by endpoint and status code
    - Add agent latency histograms (p50, p95, p99) and error rate by agent
    - Configure `structlog` JSON formatter with fields: timestamp, level, request_id, session_id, agent_name, latency_ms
    - _Requirements: 25.1, 25.2, 25.3_

  - [x] 15.3 Create Grafana dashboard configuration
    - Create `docker/grafana/provisioning/dashboards/tropicare.json` with panels for request rate, agent latency distribution, error rate by agent, active session count
    - _Requirements: 25.4_

- [x] 16. Resilience and performance
  - [x] 16.1 Implement circuit breakers for LLM and MCP calls
    - Create `backend/app/gateway/circuit_breaker.py` with `CircuitBreaker` class (CLOSED → OPEN → HALF_OPEN → CLOSED)
    - Configure: failure_threshold=5, window_seconds=60, recovery_seconds=30
    - Wrap `BaseAgent._call_claude` with `llm_breaker`
    - Wrap `MCPClient.call` with `mcp_breaker`
    - _Requirements: 29.1, 29.2, 29.3_

  - [x] 16.2 Implement graceful degradation for agent pipeline failures
    - On MCP tool failure: continue with available data, add warning annotation
    - On invalid LLM JSON: extract valid fields, discard malformed, emit validation warning
    - On all retries exhausted: return structured error event in session language
    - _Requirements: 28.1, 28.2, 28.3_

  - [x] 16.3 Implement infrastructure fallbacks
    - MongoDB fallback: fall back to BM25-only retrieval when vector search is unreachable, log error with connection details
    - Redis unavailability: return HTTP 503 for session create/turn submit
    - Empty KB: add warning annotation for no-evidence scenarios
    - _Requirements: 31.1, 31.2, 32.1, 32.2, 33.1, 33.2_

  - [x] 16.4 Implement performance caching and connection pooling
    - Cache `hybrid_retrieve` results in Redis with 1-hour TTL keyed by query hash
    - Ensure session store uses 24h TTL and limits conversation history to 20 turns
    - Configure database connection pool: min_size=2, max_size=10
    - Cache embedding vectors in Redis with 24h TTL keyed by content hash
    - _Requirements: 30.1, 30.2, 30.3, 30.4_

  - [x] 16.5 Implement session expiry and concurrent session limits
    - Return HTTP 404 for expired/missing session IDs
    - Limit each user to 5 concurrent active sessions, return HTTP 429 when exceeded
    - _Requirements: 34.1, 34.2_

  - [x] 16.6 Write property test for session history bound (Property 12)
    - **Property 12: Session conversation history bounded**
    - Use Hypothesis to generate session histories with >20 turns
    - Verify `append_turn` truncates to at most 20 entries
    - Place in `tests/property/test_session_history_bound.py`
    - **Validates: Requirement 30.2**

- [x] 17. Checkpoint — Resilience and performance verified
  - Ensure all tests pass, ask the user if questions arise.

- [x] 18. Frontend improvements
  - [x] 18.1 Implement ErrorBoundary component
    - Create class component wrapping all route-level pages
    - Catch rendering errors, display localized fallback (French/English) with retry button
    - Log error details to console
    - _Requirements: 26.1, 26.2_

  - [x] 18.2 Implement loading states and accessibility
    - Add loading indicators (skeleton/spinner) for all data-dependent components during API requests and streaming
    - Add `aria-label` attributes on all interactive elements (buttons, inputs, selects, links)
    - Use semantic HTML landmarks: `<main>`, `<nav>`, `<header>`
    - _Requirements: 27.1, 27.2_

- [x] 19. Knowledge base seeding
  - [x] 19.1 Seed CAME formulary data
    - Create Alembic migration seeding ≥80 entries in `came_formulary` with generic name, ATC code, availability status, dosage forms
    - Cover antimalarials, antibiotics, antifungals, antiparasitics, and supportive care medications
    - _Requirements: 20.1, 20.2_

  - [x] 19.2 Seed AMR, DDI, and drug safety data
    - Seed ≥50 entries in `amr_data` covering key drug-pathogen-region combinations for Togo and West Africa
    - Seed ≥30 entries in `ddi_interactions` covering clinically significant tropical disease medication interactions
    - Seed ≥40 entries in `drug_safety` covering pregnancy categories, lactation safety, and trimester-specific notes
    - _Requirements: 21.1, 21.2, 21.3_

- [x] 20. Backend unit and integration tests
  - [x] 20.1 Write unit tests for agents
    - Test `DiagnosticAgent` with mocked MCP tools: verify differential list with valid ICD-11 codes and confidence scores
    - Test `AntibiotherapyAgent` with mocked MCP tools: verify drug recommendations with dosage, route, CAME availability
    - Test `AntibiotherapyAgent` resistance logic with mocked AMR data: verify resistance profiles with percentage and confidence level
    - _Requirements: 16.1, 16.2, 16.3_

  - [x] 20.2 Write integration tests for Gateway endpoints
    - Test session creation `POST /api/v1/sessions` → HTTP 201 with valid session_id
    - Test turn submission `POST /api/v1/sessions/{id}/turns` → NDJSON streaming with expected event types
    - Test feedback submission `POST /api/v1/feedback` → HTTP 201
    - Test admin document endpoints → HTTP 403 for non-admin, HTTP 200 for admin
    - _Requirements: 16.4, 16.5, 16.6, 16.7_

- [x] 21. Frontend component tests
  - [x] 21.1 Write component tests for IntakeForm, ChatStream, and EmergencyBanner
    - Test `IntakeForm` mandatory field validation: reject submissions missing age, sex, region, or chief complaint
    - Test `ChatStream` streaming event rendering: differential cards, treatment plans, emergency banners
    - Test `EmergencyBanner` emergency flag display with urgent visual styling
    - _Requirements: 17.1, 17.2, 17.3_

- [x] 22. Evaluation framework verification
  - [x] 22.1 Verify evaluation harness functionality
    - Ensure `EvalHarness` executes benchmark cases by creating sessions, submitting turns, collecting streamed responses
    - Verify computation of top-1, top-3, top-5 accuracy, MRR, emergency recall, citation rate, guideline adherence, CAME coverage, disclaimer rate
    - Verify `BenchmarkReport` generation with per-category and per-difficulty breakdowns
    - _Requirements: 18.1, 18.2, 18.3, 18.4_

- [x] 23. Documentation
  - [x] 23.1 Create README.md and API documentation
    - Write `README.md` with project overview, architecture description, prerequisites, local development setup, environment variable reference
    - Write API documentation covering all Gateway endpoints with request/response schemas, auth requirements, example curl commands
    - _Requirements: 19.1, 19.2_

  - [x] 23.2 Create deployment guide
    - Write deployment guide with Docker Compose production configuration, JWT secret management, database migration steps, knowledge base seeding instructions, monitoring setup
    - _Requirements: 19.3_

- [x] 24. Final checkpoint — Full platform verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate the 12 correctness properties defined in the design document
- Backend uses Python (FastAPI, Pydantic, Hypothesis for PBT); frontend uses TypeScript (Next.js, React)
- The MongoDB migration (task 5) must complete before agent intelligence tasks (11–13) since agents depend on MCP tools using MongoDB
- Test directory structure (task 4) is set up early so property test tasks throughout the plan have their target directories available
