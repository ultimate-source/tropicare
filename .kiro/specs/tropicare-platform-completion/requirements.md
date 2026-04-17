# Requirements Document

## Introduction

TropiCare is an AI-powered clinical decision support system for tropical disease diagnosis and antibiotherapy recommendations in Togo. The platform uses a multi-agent pipeline (Intake, Diagnostic, Antibiotherapy, Validation) backed by a RAG knowledge base, with a FastAPI gateway and Next.js frontend. This document specifies the requirements for completing all unfinished areas of the platform: agent intelligence, authentication, testing, documentation, knowledge base seeding, security hardening, observability, frontend improvements, error handling, and performance optimization.

## Glossary

- **Intake_Agent**: The agent responsible for extracting and structuring patient context from free-text clinical notes using NLP entity extraction and LLM parsing (class IntakeAgent in base.py)
- **Diagnostic_Agent**: The agent responsible for differential diagnosis reasoning using RAG context and epidemiological priors for Togo (class DiagnosticAgent in base.py, replacing the stub in diagnostic_agent.py)
- **Treatment_Agent**: The agent responsible for generating antibiotherapy recommendations based on WHO/PNLP protocols, local drug availability, and resistance data (class AntibiotherapyAgent in base.py, replacing the stub in treatment_agent.py)
- **Resistance_Agent**: The agent responsible for querying AMR data via MCP tools and cross-referencing WHO resistance data (to be implemented, replacing the stub in resistance_agent.py)
- **Validation_Agent**: The agent responsible for verifying LLM output quality including citation presence, numeric consistency, emergency flag handling, and language compliance before streaming to the clinician (class ValidationAgent in base.py)
- **Orchestrator**: The component that coordinates the multi-agent pipeline (Intake → Diagnostic → Antibiotherapy → Validation) and streams NDJSON events to the client
- **Gateway**: The FastAPI application that exposes REST/streaming endpoints, handles JWT authentication, and routes requests to the Orchestrator
- **MCP_Tools_Server**: The FastMCP server providing clinical knowledge tools (hybrid retrieval, formulary lookup, AMR lookup, DDI check, safety classifier, epidemiological calendar)
- **Session_Store**: The Redis-backed session store managing patient context and conversation history with configurable TTL
- **Audit_Logger**: The immutable append-only audit log writer persisting events to the partitioned PostgreSQL audit_log table
- **Knowledge_Base**: The combined PostgreSQL (full-text) and MongoDB Atlas Vector Search (vector) stores containing clinical guidelines, formulary data, AMR profiles, DDI interactions, and drug safety data
- **CAME_Formulary**: The Centrale d'Achat des Médicaments Essentiels — Togo's national essential medicines list
- **PNLP**: Programme National de Lutte contre le Paludisme — Togo's national malaria control program
- **AMR**: Antimicrobial Resistance — resistance patterns of pathogens to specific drugs
- **DDI**: Drug-Drug Interaction — clinically significant interactions between co-administered medications
- **Eval_Harness**: The benchmark framework that runs clinical test cases through the pipeline and computes diagnostic and treatment accuracy metrics
- **Frontend**: The Next.js 14+ application with App Router providing the clinical chat interface, intake form, and admin dashboard
- **RBAC**: Role-Based Access Control — authorization mechanism restricting endpoints based on user roles (clinician, admin)
- **Testing_Suite**: The collection of unit tests, integration tests, frontend component tests, and property-based tests verifying platform correctness
- **Observability_Stack**: The combination of Jaeger (tracing), Prometheus (metrics), Grafana (dashboards), and structlog (logging) providing operational visibility
- **Ingestion_Pipeline**: The document processing pipeline that parses, chunks, embeds, and stores clinical documents into the Knowledge_Base
- **Documentation**: The set of README, API reference, and deployment guide files describing the platform
- **Codebase**: The project file and directory structure encompassing both backend (Python) and frontend (TypeScript/React) source code

## Requirements

### Requirement 1: Backend Agent Module Restructuring

**User Story:** As a developer, I want each agent in its own module file with clear separation of concerns, so that the codebase is navigable and maintainable.

#### Acceptance Criteria

1. THE Codebase SHALL organize agent implementations into separate files: backend/app/agents/intake.py, backend/app/agents/diagnostic.py, backend/app/agents/antibiotherapy.py, and backend/app/agents/validation.py, extracted from the current monolithic base.py
2. THE Codebase SHALL retain backend/app/agents/base.py containing only the BaseAgent abstract class, AgentSpan model, and MCPClient utility class
3. THE Codebase SHALL remove the stub files backend/app/agents/diagnostic_agent.py, backend/app/agents/treatment_agent.py, backend/app/agents/resistance_agent.py, and backend/app/agents/orchestrator.py that conflict with the full implementations
4. THE Codebase SHALL update all import statements across the backend to reference the new module paths after restructuring

### Requirement 2: Backend Duplicate and Dead Code Removal

**User Story:** As a developer, I want conflicting and unused code removed, so that there is a single source of truth for each component.

#### Acceptance Criteria

1. THE Codebase SHALL remove backend/app/api/routes.py and backend/app/api/__init__.py which duplicate the Gateway routes in backend/app/gateway/main.py
2. THE Codebase SHALL remove backend/app/rag/retriever.py which references ChromaDB while the production system uses MongoDB Atlas Vector Search via the MCP_Tools_Server
3. THE Codebase SHALL remove the current backend/app/config/settings.py which conflicts with the Gateway configuration in backend/app/gateway/config.py
4. THE Codebase SHALL contain a single consolidated backend/app/config/settings.py that serves both the Gateway and MCP_Tools_Server
5. THE consolidated backend/app/config/settings.py SHALL include all required environment variables: ANTHROPIC_API_KEY, OPENAI_API_KEY, DATABASE_URL, REDIS_URL, MONGODB_URI, MONGODB_DB, MCP_URL, MODEL, CORS_ORIGINS, and JWT_PUBLIC_KEY_PATH
6. THE Codebase SHALL fix the missing "import os" in backend/app/gateway/auth.py
7. THE Codebase SHALL fix the incorrect "from typing import list" (should be "from typing import List" or use built-in list) in backend/app/gateway/config.py

### Requirement 3: Backend Models and Schemas Consolidation

**User Story:** As a developer, I want a single authoritative set of Pydantic models matching the actual data structures used by agents and the Gateway, so that type safety is maintained across the codebase.

#### Acceptance Criteria

1. THE Codebase SHALL update backend/app/models/schemas.py to include all Pydantic models used by the agents: PatientContext, DiagnosticDifferential, DiagnosisItem, TreatmentPlan, DrugRegimen, AMRProfile, DDIWarning, and ConsultationResponse
2. THE Codebase SHALL ensure all agent implementations import models from backend/app/models/schemas.py rather than defining inline dictionaries
3. THE Codebase SHALL include a PatientContext Pydantic model matching the fields defined in the frontend IntakeForm component: age_years (int), sex (literal "M" or "F"), weight_kg (float or null), region (str), chief_complaint (str), symptoms (list of objects with a "text" string field), vital_signs (optional object), lab_results (list of objects with name, value, unit string fields), current_medications (list of objects with name, dose, frequency string fields), allergies (list of str), pregnancy_status (str), symptom_onset_days (int or null), travel_history (list of str)

### Requirement 4: Frontend Type and File Consolidation

**User Story:** As a developer, I want a single source of truth for TypeScript types and no duplicate or legacy files, so that the frontend codebase is clean and type-safe.

#### Acceptance Criteria

1. THE Codebase SHALL consolidate frontend/src/types/index.ts and frontend/src/lib/types.ts into a single frontend/src/lib/types.ts file containing all shared domain types
2. THE Codebase SHALL remove the duplicate frontend/src/globals.css file, retaining only frontend/src/app/globals.css as the single global stylesheet
3. THE Codebase SHALL remove legacy components frontend/src/components/ResultsPanel.tsx and frontend/src/components/SymptomForm.tsx that are unused by the current chat-based interface
4. THE Codebase SHALL update all frontend import statements to reference the consolidated type file after restructuring

### Requirement 5: Test Directory Structure

**User Story:** As a developer, I want a well-organized test directory structure, so that tests are discoverable and follow project conventions.

#### Acceptance Criteria

1. THE Codebase SHALL organize backend tests in a tests/ directory at the project root with subdirectories: tests/unit/agents/, tests/unit/tools/, tests/integration/api/, and tests/integration/orchestrator/
2. THE Codebase SHALL organize frontend tests in a frontend/__tests__/ directory with subdirectories: frontend/__tests__/components/ and frontend/__tests__/hooks/
3. THE Codebase SHALL include pytest configuration in a pyproject.toml or pytest.ini at the project root with test discovery paths and markers for unit, integration, and property-based tests

### Requirement 6: Diagnostic Agent RAG Retrieval

**User Story:** As a clinician, I want the Diagnostic Agent to retrieve relevant clinical guidelines and epidemiological data, so that differential diagnoses are grounded in evidence.

#### Acceptance Criteria

1. WHEN a ConsultationRequest is submitted with symptoms and region, THE Diagnostic_Agent SHALL invoke the MCP hybrid_retrieve tool with at least two query expansions (symptom-based and epidemiological)
2. WHEN the Diagnostic_Agent completes retrieval and reasoning, THE Diagnostic_Agent SHALL return between 3 and 5 ranked diagnoses in the differential output
3. WHEN the patient region and current month are provided, THE Diagnostic_Agent SHALL invoke the epid_calendar MCP tool and integrate seasonal disease priors into confidence scoring
4. WHEN the Diagnostic_Agent requires additional evidence during ReAct reasoning, THE Diagnostic_Agent SHALL signal retrieval queries and perform up to 4 ReAct iterations, incorporating newly retrieved chunks before producing the final differential

### Requirement 7: Diagnostic Agent Output Structure

**User Story:** As a clinician, I want each diagnosis in the differential to include structured clinical data, so that I can evaluate the reasoning and plan next steps.

#### Acceptance Criteria

1. WHEN the Diagnostic_Agent produces a differential diagnosis, THE Diagnostic_Agent SHALL include for each diagnosis a disease name and an ICD-11 code
2. WHEN the Diagnostic_Agent produces a differential diagnosis, THE Diagnostic_Agent SHALL include for each diagnosis a confidence score between 0.0 and 1.0 with a list of one or more supporting evidence strings, each referencing a specific Knowledge_Base chunk ID
3. WHEN the Diagnostic_Agent produces a differential diagnosis, THE Diagnostic_Agent SHALL include for each diagnosis a list of confirmatory tests with Togo availability status (available, limited, unavailable)
4. WHEN the Diagnostic_Agent identifies a critical condition (meningitis, severe malaria, viral hemorrhagic fever, or septic shock), THE Diagnostic_Agent SHALL emit an emergency_flag event before emitting any diagnostic content

### Requirement 8: Diagnostic Agent Output Validation

**User Story:** As a clinician, I want the system to validate LLM output before presenting it, so that I receive well-structured diagnostic information.

#### Acceptance Criteria

1. IF the LLM returns output that does not parse as valid JSON matching the differential schema, THEN THE Diagnostic_Agent SHALL retry the LLM call once before returning a structured error event
2. WHEN the Diagnostic_Agent produces valid output, THE Validation_Agent SHALL verify citation presence, numeric consistency, emergency flag handling, and language compliance before the output is streamed to the clinician

### Requirement 9: Treatment Agent Protocol Retrieval

**User Story:** As a clinician, I want the Treatment Agent to retrieve WHO/PNLP treatment protocols, so that recommendations follow established clinical guidelines.

#### Acceptance Criteria

1. WHEN a confirmed diagnosis with confidence score is provided, THE Treatment_Agent SHALL retrieve treatment guidelines via MCP hybrid_retrieve using at least three query expansions (PNLP protocol, antibiotherapy guidelines, WHO posology)
2. WHEN generating a treatment recommendation for a candidate drug, THE Treatment_Agent SHALL invoke the formulary_lookup MCP tool and indicate CAME availability status in the output
3. WHEN generating a treatment recommendation, THE Treatment_Agent SHALL invoke the amr_lookup MCP tool and deprioritize any antibiotic with resistance above 30% in the patient region

### Requirement 10: Treatment Agent Dosage and Safety

**User Story:** As a clinician, I want treatment recommendations adapted to patient demographics and safety constraints, so that prescribing guidance is safe and personalized.

#### Acceptance Criteria

1. WHEN the patient age and weight are provided, THE Treatment_Agent SHALL calculate dosage in mg/kg for pediatric patients and include route, frequency, and duration for each recommended drug
2. WHEN the patient pregnancy status indicates pregnancy, THE Treatment_Agent SHALL invoke the safety_classifier MCP tool and include only FDA category A, B, or C drugs with trimester-specific safety notes
3. WHEN the patient has current medications, THE Treatment_Agent SHALL invoke the drug_ddi_check MCP tool and emit severity-tagged interaction warnings for each detected DDI
4. THE Treatment_Agent SHALL append the regulatory disclaimer text to every treatment plan output

### Requirement 11: Resistance Agent Database Integration

**User Story:** As a clinician, I want the Resistance Agent to provide current local AMR data for the patient's region, so that treatment recommendations account for resistance patterns.

#### Acceptance Criteria

1. WHEN a diagnostic result and region are provided, THE Resistance_Agent SHALL invoke the amr_lookup MCP tool for resistance profiles matching the inferred pathogens and patient region
2. IF no Togo-specific AMR data exists for a drug-pathogen pair, THEN THE Resistance_Agent SHALL invoke the amr_lookup MCP tool with region "West Africa" and indicate the fallback data source in the response
3. WHEN AMR data is returned, THE Resistance_Agent SHALL include resistance percentage, confidence level (high, medium, low, or no_data), data source, and year for each drug-pathogen pair
4. IF no AMR data is available for any queried drug-pathogen pair, THEN THE Resistance_Agent SHALL return a structured response indicating data unavailability and recommend the empirical PNLP protocol

### Requirement 12: Orchestrator Clinical Alerts and References

**User Story:** As a clinician, I want the Orchestrator to generate clinical warnings and collect source references, so that I am alerted to critical findings and can verify the evidence basis.

#### Acceptance Criteria

1. WHEN the diagnostic result contains emergency flags, THE Orchestrator SHALL generate clinical warning messages and include them in the ConsultationResponse warnings list
2. WHEN resistance data indicates resistance above 30% for a recommended drug, THE Orchestrator SHALL add a high-resistance warning to the ConsultationResponse warnings list
3. WHEN a drug-drug interaction with severity "contraindicated" or "major" is detected, THE Orchestrator SHALL add a warning specifying the interacting drugs and recommended management to the ConsultationResponse warnings list
4. WHEN the diagnostic and treatment results contain citations, THE Orchestrator SHALL collect and deduplicate all references into the ConsultationResponse references list with source attribution (OMS, PNLP, MSF)

### Requirement 13: User Registration

**User Story:** As a system administrator, I want a user registration endpoint with secure password storage, so that new clinicians can be onboarded to the platform.

#### Acceptance Criteria

1. WHEN a registration request is submitted with email, password, and role, THE Gateway SHALL hash the password using bcrypt with a cost factor of at least 12 and store the user record in the users table
2. WHEN a registration request is submitted with an email that already exists in the users table, THE Gateway SHALL return HTTP 409 with a message indicating the email is already registered
3. WHEN a registration request is submitted, THE Gateway SHALL validate the password contains at least 10 characters, one uppercase letter, one lowercase letter, and one digit

### Requirement 14: Authentication and Token Management

**User Story:** As a clinician, I want secure login with token refresh and account protection, so that my sessions are secure and persistent.

#### Acceptance Criteria

1. WHEN a login request is submitted with valid credentials, THE Gateway SHALL return a signed JWT (RS256) access token with an 8-hour expiry and a refresh token with a 30-day expiry
2. WHEN a refresh token request is submitted with a valid non-expired refresh token, THE Gateway SHALL issue a new access token and rotate the refresh token
3. IF an expired or malformed JWT is presented, THEN THE Gateway SHALL return HTTP 401 with a descriptive error message
4. WHEN a user fails authentication 5 times consecutively for the same email within 30 minutes, THE Gateway SHALL lock the account for 15 minutes and return HTTP 423

### Requirement 15: Role-Based Access Control

**User Story:** As a system administrator, I want endpoints protected by role-based access control, so that only authorized users access sensitive functionality.

#### Acceptance Criteria

1. WHEN a user attempts to access an endpoint requiring the "admin" role, THE Gateway SHALL verify the JWT roles claim contains "admin" and return HTTP 403 if the role is absent
2. WHEN a user attempts to access an endpoint requiring the "clinician" role, THE Gateway SHALL verify the JWT roles claim contains "clinician" and return HTTP 403 if the role is absent
3. THE Gateway SHALL require the "admin" role for document management endpoints and analytics endpoints
4. THE Gateway SHALL require the "clinician" role for session creation, turn submission, and feedback endpoints

### Requirement 16: Unit and Integration Testing

**User Story:** As a developer, I want unit tests for agents and integration tests for API routes, so that backend correctness is verified.

#### Acceptance Criteria

1. THE Testing_Suite SHALL include unit tests for Diagnostic_Agent that mock MCP tool calls and verify the output contains a differential list with valid ICD-11 codes and confidence scores
2. THE Testing_Suite SHALL include unit tests for Treatment_Agent that mock MCP tool calls and verify the output contains drug recommendations with dosage, route, and CAME availability
3. THE Testing_Suite SHALL include unit tests for Resistance_Agent that mock database queries and verify the output contains resistance profiles with percentage and confidence level
4. THE Testing_Suite SHALL include integration tests for Gateway session creation (POST /api/v1/sessions) verifying HTTP 201 response with a valid session_id
5. THE Testing_Suite SHALL include integration tests for Gateway turn submission (POST /api/v1/sessions/{id}/turns) verifying NDJSON streaming response with expected event types
6. THE Testing_Suite SHALL include integration tests for Gateway feedback submission (POST /api/v1/feedback) verifying HTTP 201 response
7. THE Testing_Suite SHALL include integration tests for Gateway admin document endpoints verifying HTTP 403 for non-admin users and HTTP 200 for admin users

### Requirement 17: Frontend and Property-Based Testing

**User Story:** As a developer, I want frontend component tests and property-based tests, so that UI correctness and data invariants are verified.

#### Acceptance Criteria

1. THE Testing_Suite SHALL include component tests for IntakeForm verifying that mandatory field validation rejects submissions missing age, sex, region, or chief complaint
2. THE Testing_Suite SHALL include component tests for ChatStream verifying that streaming events render differential cards, treatment plans, and emergency banners
3. THE Testing_Suite SHALL include component tests for EmergencyBanner verifying that emergency flags display with urgent visual styling
4. WHEN a valid PatientContext object is serialized to JSON and deserialized back, THE result SHALL be equivalent to the original PatientContext object (round-trip property)
5. WHEN a valid ConsultationRequest with non-empty symptoms is processed by the Diagnostic_Agent output parser, THE parser SHALL produce a result matching the differential schema or raise a structured ValueError (parser correctness property)
6. FOR ALL valid differential diagnosis outputs, THE confidence scores SHALL each be within the range [0.0, 1.0] (confidence score invariant property)
7. FOR ALL valid treatment plan outputs, THE disclaimer field SHALL be present and contain the mandatory regulatory disclaimer text (disclaimer invariant property)
8. FOR ALL streaming event sequences produced by the Orchestrator, THE emergency_flag events SHALL precede all differential_item events in emission order (emergency ordering invariant property)
9. FOR ALL ConsultationResponse objects produced by the Orchestrator, THE references list SHALL contain no duplicate entries when compared by source title and section (citation deduplication invariant property)

### Requirement 18: Evaluation Framework

**User Story:** As a developer, I want the evaluation harness to run benchmark cases and compute accuracy metrics, so that diagnostic and treatment quality can be measured.

#### Acceptance Criteria

1. THE Eval_Harness SHALL execute benchmark cases by creating sessions, submitting turns, and collecting streamed responses
2. WHEN a benchmark run completes, THE Eval_Harness SHALL compute top-1, top-3, and top-5 diagnostic accuracy and mean reciprocal rank (MRR)
3. WHEN a benchmark run completes, THE Eval_Harness SHALL compute emergency recall, citation rate, guideline adherence, CAME coverage, and disclaimer rate metrics
4. WHEN a benchmark run completes, THE Eval_Harness SHALL generate a BenchmarkReport with per-category and per-difficulty breakdowns

### Requirement 19: Documentation

**User Story:** As a developer or operator, I want comprehensive README, API documentation, and deployment guide, so that the platform can be understood, used, and deployed.

#### Acceptance Criteria

1. THE Documentation SHALL include a README.md with project overview, architecture description, prerequisites, local development setup instructions, and environment variable reference
2. THE Documentation SHALL include API documentation covering all Gateway endpoints with request and response schemas, authentication requirements, and example curl commands
3. THE Documentation SHALL include a deployment guide with Docker Compose production configuration, secret management for JWT keys, database migration steps, knowledge base seeding instructions, and monitoring setup

### Requirement 20: Knowledge Base Formulary Seeding

**User Story:** As a system administrator, I want the CAME formulary seeded with comprehensive tropical disease medication data, so that the Treatment Agent can check drug availability.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL contain at least 80 entries in the came_formulary table with generic name, ATC code, availability status, and dosage forms
2. THE Knowledge_Base SHALL include formulary entries covering antimalarials, antibiotics, antifungals, antiparasitics, and supportive care medications used in Togo

### Requirement 21: Knowledge Base AMR and Safety Seeding

**User Story:** As a system administrator, I want AMR, DDI, and drug safety data seeded, so that the agents have resistance, interaction, and pregnancy safety reference data.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL contain at least 50 entries in the amr_data table covering key drug-pathogen-region combinations for Togo and West Africa with resistance percentages and confidence levels
2. THE Knowledge_Base SHALL contain at least 30 entries in the ddi_interactions table covering clinically significant interactions between tropical disease medications with severity, mechanism, clinical effect, and management
3. THE Knowledge_Base SHALL contain at least 40 entries in the drug_safety table covering pregnancy categories (A through X), lactation safety, and trimester-specific notes for tropical disease medications

### Requirement 22: Security Response Headers

**User Story:** As a security officer, I want the Gateway to set protective HTTP headers, so that common browser-based attacks are mitigated.

#### Acceptance Criteria

1. THE Gateway SHALL set the X-Content-Type-Options response header to "nosniff" on every response
2. THE Gateway SHALL set the X-Frame-Options response header to "DENY" on every response
3. THE Gateway SHALL set the Strict-Transport-Security response header with max-age of 31536000 seconds on every response
4. THE Gateway SHALL set the Content-Security-Policy response header on every API response with a policy that restricts default-src to 'self' (note: the frontend Next.js server may require additional CSP directives for scripts and styles)

### Requirement 23: Input Validation and Data Protection

**User Story:** As a security officer, I want all inputs validated and patient data anonymized in audit logs, so that the platform is protected against injection attacks and compliant with data protection.

#### Acceptance Criteria

1. THE Gateway SHALL validate all request body string fields using Pydantic models with a maximum length constraint of 5000 characters
2. THE Gateway SHALL validate all request body region fields against the enumeration (Maritime, Plateaux, Centrale, Kara, Savanes)
3. THE Gateway SHALL validate all request body email fields using regex pattern matching
4. WHEN writing to the audit_log table, THE Audit_Logger SHALL replace patient-identifiable fields in the payload (age_years, weight_kg, chief_complaint, symptoms text, allergies) with SHA-256 hashed values before persistence
5. THE Gateway SHALL enforce rate limiting of 30 requests per minute for session creation, 60 requests per minute for turn submission, and 10 requests per minute for authentication endpoints
6. THE Gateway SHALL implement CSRF protection using the double-submit cookie pattern for all state-changing endpoints accessed from browser clients

### Requirement 24: OpenTelemetry Tracing

**User Story:** As an operations engineer, I want distributed tracing exported to Jaeger, so that I can trace requests across the multi-agent pipeline.

#### Acceptance Criteria

1. THE Gateway SHALL export OpenTelemetry traces to Jaeger for every API request with a unique trace ID
2. WHEN an agent executes, THE Gateway SHALL create a child span with attributes for agent name, latency in milliseconds, input token count, output token count, and verdict (ok, error, or blocked)
3. WHEN an MCP tool is invoked, THE MCP_Tools_Server SHALL create a span with attributes for tool name and result count

### Requirement 25: Prometheus Metrics and Structured Logging

**User Story:** As an operations engineer, I want Prometheus metrics and structured JSON logging, so that I can monitor system health and search logs efficiently.

#### Acceptance Criteria

1. THE Gateway SHALL expose a Prometheus-compatible /metrics endpoint reporting request count by endpoint and status code
2. THE Gateway SHALL expose agent latency histograms (p50, p95, p99) and error rate by agent on the /metrics endpoint
3. THE Gateway SHALL use structlog for all application logging with JSON output format including fields: timestamp, level, request_id, session_id, agent_name, and latency_ms
4. THE Observability_Stack SHALL include a Grafana dashboard JSON configuration with panels for request rate, agent latency distribution, error rate by agent, and active session count

### Requirement 26: Frontend Error Boundaries

**User Story:** As a clinician, I want the frontend to catch rendering errors gracefully, so that a component failure does not crash the entire application.

#### Acceptance Criteria

1. THE Frontend SHALL wrap all route-level pages in an ErrorBoundary component that catches rendering errors and displays a fallback message with a retry action
2. IF a child component throws an error during rendering, THEN THE ErrorBoundary SHALL log the error details and display a localized error message in the session language (French or English)

### Requirement 27: Frontend Loading States and Accessibility

**User Story:** As a clinician, I want loading indicators during operations and accessible interactive elements, so that the interface communicates status and is usable with assistive technologies.

#### Acceptance Criteria

1. WHILE an API request or streaming operation is in progress, THE Frontend SHALL display a loading indicator (skeleton or spinner) for all data-dependent components
2. THE Frontend SHALL include ARIA labels on all interactive elements (buttons, inputs, selects, links) and use semantic HTML landmarks (main, nav, header) for screen reader navigation
3. WHEN the IntakeForm onComplete callback is invoked, THE Frontend SHALL accept a PatientContext typed parameter, resolving the TypeScript type mismatch in chat/page.tsx where Record<string, unknown> is used instead of PatientContext

### Requirement 28: Graceful Degradation on Tool Failure

**User Story:** As a clinician, I want the system to continue providing partial results when individual tools fail, so that I receive the best available information.

#### Acceptance Criteria

1. WHEN an MCP tool call fails during agent execution, THE Orchestrator SHALL continue processing with available data and include a warning annotation indicating which tool data is missing
2. WHEN the LLM returns output that does not conform to the expected JSON schema, THE Orchestrator SHALL extract any valid JSON fields that conform to the expected schema, discard non-conforming fields, and emit a validation warning annotation listing the missing or malformed fields
3. IF all retry attempts for the Diagnostic_Agent or Treatment_Agent are exhausted, THEN THE Orchestrator SHALL return a structured error event with a clinician-facing message in the session language

### Requirement 29: Circuit Breaker for External APIs

**User Story:** As an operations engineer, I want circuit breakers on external API calls, so that cascading failures are prevented when upstream services are degraded.

#### Acceptance Criteria

1. THE Gateway SHALL implement a circuit breaker for LLM API calls that opens after 5 consecutive failures within 60 seconds
2. WHEN the circuit breaker is open, THE Gateway SHALL return a service-unavailable error immediately for 30 seconds before attempting a probe request to check recovery
3. THE Gateway SHALL implement a circuit breaker for MCP tool calls with the same thresholds (5 failures within 60 seconds, 30-second recovery)

### Requirement 30: Performance Caching

**User Story:** As a clinician, I want fast response times for consultations, so that the system supports real-time clinical workflows.

#### Acceptance Criteria

1. THE MCP_Tools_Server SHALL cache hybrid_retrieve results in Redis with a 1-hour TTL keyed by a hash of the query, disease tags, and language parameters
2. THE Session_Store SHALL maintain session data in Redis with a 24-hour TTL and limit conversation history to the 20 most recent turns
3. THE Gateway SHALL maintain a database connection pool supporting at least 10 concurrent queries with a minimum of 2 idle connections
4. THE Ingestion_Pipeline SHALL cache embedding vectors in Redis with a 24-hour TTL keyed by content hash to avoid re-embedding unchanged document chunks

### Requirement 31: MongoDB Atlas Vector Search Unavailability Fallback

**User Story:** As a clinician, I want the system to provide results even when the vector store is unavailable, so that I am not blocked by infrastructure failures.

#### Acceptance Criteria

1. IF MongoDB Atlas Vector Search is unreachable during a hybrid_retrieve call, THEN THE MCP_Tools_Server SHALL fall back to BM25-only retrieval from PostgreSQL and include a warning annotation indicating reduced retrieval quality
2. IF MongoDB Atlas Vector Search is unreachable, THEN THE MCP_Tools_Server SHALL log the connection failure with error details and MongoDB connection URI

### Requirement 32: Redis Unavailability Handling

**User Story:** As a clinician, I want clear feedback when the session store is unavailable, so that I understand why the system cannot process my request.

#### Acceptance Criteria

1. IF Redis is unreachable during session creation, THEN THE Gateway SHALL return HTTP 503 with a message indicating the session service is temporarily unavailable
2. IF Redis is unreachable during turn submission, THEN THE Gateway SHALL return HTTP 503 with a message indicating the session could not be loaded

### Requirement 33: Empty Knowledge Base Handling

**User Story:** As a clinician, I want informative feedback when the knowledge base has no relevant data, so that I understand the limitations of the system response.

#### Acceptance Criteria

1. WHEN the hybrid_retrieve tool returns zero chunks for all query expansions, THE Diagnostic_Agent SHALL include a warning annotation stating that no knowledge base evidence was found and that the differential is based on the LLM general knowledge only
2. WHEN the hybrid_retrieve tool returns zero chunks for treatment queries, THE Treatment_Agent SHALL include a warning annotation stating that no guideline evidence was found and recommend consulting local PNLP protocols directly

### Requirement 34: Session Expiry and Concurrent Session Limits

**User Story:** As a clinician, I want clear feedback when my session has expired and reasonable limits on concurrent sessions, so that the system behaves predictably.

#### Acceptance Criteria

1. WHEN a turn submission references a session ID that has expired or does not exist in Redis, THE Gateway SHALL return HTTP 404 with a message indicating the session has expired and a new session must be created
2. THE Gateway SHALL limit each user to a maximum of 5 concurrent active sessions and return HTTP 429 when the limit is exceeded during session creation


### Requirement 35: MongoDB Atlas Vector Search Migration

**User Story:** As a developer, I want the vector search infrastructure migrated from Qdrant to MongoDB Atlas Vector Search, so that the codebase matches the production architecture described in the design.

#### Acceptance Criteria

1. THE MCP_Tools_Server SHALL replace all Qdrant client imports and calls in backend/app/tools/server.py with MongoDB Atlas Vector Search queries using the motor AsyncIOMotorClient and the $vectorSearch aggregation pipeline stage
2. THE MCP_Tools_Server SHALL contain a backend/app/tools/db.py module providing a MongoDB connection singleton (motor.AsyncIOMotorClient) alongside the existing PostgreSQL pool and Redis singletons
3. THE MCP_Tools_Server SHALL define a MongoDB Atlas Vector Search index on the kb_vectors collection with dimensions 3072, similarity metric cosine, and path "embedding" for the vector field
4. THE Ingestion_Pipeline SHALL replace all Qdrant client imports and calls in backend/app/ingestion/store.py and backend/app/ingestion/pipeline.py with MongoDB insert operations that store chunk metadata and embedding vectors in the kb_vectors collection
5. THE Codebase SHALL update docker-compose.yml to remove the qdrant service, qdrant-init bootstrap service, and qdrant_data volume, and replace QDRANT_URL and QDRANT_COLLECTION environment variables with MONGODB_URI and MONGODB_DB
6. THE Codebase SHALL add a MongoDB service to docker-compose.yml for local development (or document that Atlas is used in production with a local MongoDB replica set for development)
7. THE kb_vectors MongoDB collection SHALL store documents with fields: chunk_id (string), document_id (string), chunk_text (string), embedding (array of 3072 floats), section (string), page (int), language (string), disease_tags (array of strings), drug_tags (array of strings), content_type (string), superseded (boolean), source_title (string), source_version (string), and source_date (string)
