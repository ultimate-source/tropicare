# Requirements Document

## Introduction

The TropiCare application stores clinical session data (patient context, conversation history, diagnostic results, treatment plans, citations) exclusively in Redis with a 24-hour TTL. The PostgreSQL database already contains `sessions` and `turns` tables (created in migration 0001 with columns for `user_id`, `patient_context` JSONB, `language`, `created_at`, `expires_at`, and turn `response` JSONB), but the application code never writes to them — all session I/O goes through the Redis `SessionStore` class. When sessions expire from Redis, clinicians lose access to past consultation data, the session history page shows incomplete results, and the audit trail lacks clinical detail. This feature activates the existing PostgreSQL session schema by introducing a dual-write pattern so that session data flows to both Redis (for active session performance) and PostgreSQL (for long-term persistence), and adds lifecycle columns via a new Alembic migration.

## Glossary

- **Session_Store**: The Redis-backed component (`SessionStore` class) responsible for ephemeral session storage with 24-hour TTL
- **Session_Repository**: The new PostgreSQL-backed component responsible for persistent session and turn storage
- **Dual_Write_Layer**: The coordination layer that writes session data to both Redis (for active session performance) and PostgreSQL (for long-term persistence) during session lifecycle events
- **Turn_Record**: A JSON object containing the turn_id, clinician query, diagnostic results, antibiotherapy results, warnings, and references produced during a single orchestrator turn
- **Patient_Context**: A JSON object containing patient demographic and clinical information (age, sex, chief complaint, region, symptoms, allergies)
- **Session_Summary**: A lightweight representation of a session containing id, created_at, language, turn_count, and last_query, used for the session history list
- **Session_Detail**: The full session representation containing session metadata, patient_context, and an ordered list of Turn_Records
- **Gateway**: The FastAPI application (`main.py`) that exposes REST endpoints for session management
- **Orchestrator**: The component that routes clinical queries through the agent pipeline and persists turn results
- **Alembic_Migration**: A versioned database schema change script managed by the Alembic migration framework
- **Retention_Policy**: The configurable rule defining how long persistent session data is kept before archival or deletion
- **Frontend_Proxy**: The Next.js API route layer that forwards authenticated requests from the frontend to the Gateway

## Requirements

### Requirement 1: Persist Session Creation to PostgreSQL

**User Story:** As a clinician, I want my session data saved to persistent storage when I start a consultation, so that the session metadata is not lost when Redis TTL expires.

#### Acceptance Criteria

1. WHEN a new session is created via the Gateway, THE Dual_Write_Layer SHALL write the session record (session_id, user_id, patient_context, language, created_at) to both Redis and the PostgreSQL sessions table within the same request lifecycle
2. IF the PostgreSQL write fails during session creation, THEN THE Gateway SHALL log the error at WARNING level with the session_id and error message, and return the session_id to the clinician with HTTP 201
3. THE Session_Repository SHALL store the user_id foreign key on every persisted session record so that sessions can be queried by owning user

### Requirement 2: Persist Turn Data to PostgreSQL

**User Story:** As a clinician, I want each consultation turn (my query and the system's diagnostic/treatment response) saved persistently, so that I can review past diagnoses and treatment plans after the Redis session expires.

#### Acceptance Criteria

1. WHEN the Orchestrator completes a turn, THE Dual_Write_Layer SHALL write the Turn_Record (turn_id, session_id, turn_index, query, diagnostic results, antibiotherapy results, warnings, references) to the PostgreSQL turns table
2. THE Session_Repository SHALL store the diagnostic results, antibiotherapy results, warnings, and references as JSONB in the turns.response column
3. IF the PostgreSQL turn write fails, THEN THE Dual_Write_Layer SHALL log the error at WARNING level with session_id and turn_id, and continue the streaming response to the clinician
4. WHEN a turn is persisted, THE Session_Repository SHALL record the turn_index as a monotonically increasing integer within the session so that turns can be replayed in chronological order

### Requirement 3: Session History API Reads from PostgreSQL

**User Story:** As a clinician, I want the session history page to show all my past consultations including expired ones, so that I have a complete view of my consultation history.

#### Acceptance Criteria

1. WHEN the Gateway receives a GET request to /api/v1/sessions, THE Session_Repository SHALL query PostgreSQL for all non-archived sessions belonging to the authenticated user, ordered by created_at descending
2. THE Session_Repository SHALL return a list of Session_Summary objects containing id, created_at, language, turn_count, and last_query for each session
3. THE Session_Repository SHALL compute turn_count from the count of persisted turns in the turns table for each session
4. THE Session_Repository SHALL compute last_query from the query column of the most recent turn (by turn_index) for each session
5. WHEN a session exists in both Redis and PostgreSQL, THE Gateway SHALL use the PostgreSQL record as the authoritative source for the session list to avoid duplicates
6. THE Session_Repository SHALL accept optional limit and offset parameters for pagination, defaulting to limit=50 and offset=0 when not provided

### Requirement 4: Session Detail API Falls Back to PostgreSQL

**User Story:** As a clinician, I want to view the full details of any past consultation including diagnostic results and treatment plans, so that I can review previous clinical decisions even after the session has expired from Redis.

#### Acceptance Criteria

1. WHEN the Gateway receives a GET request to /api/v1/sessions/{session_id}, THE Gateway SHALL first attempt to read the session from Redis
2. IF the session is not found in Redis, THEN THE Gateway SHALL query the Session_Repository for the session record and its associated turns from PostgreSQL
3. THE Gateway SHALL return the Session_Detail containing session_id, patient_context, language, created_at, and a conversation_history array of Turn_Records ordered by turn_index
4. IF the session is not found in either Redis or PostgreSQL, THEN THE Gateway SHALL return HTTP 404 with a detail message "Session not found"

### Requirement 5: Alembic Migration for Session Persistence Schema

**User Story:** As a developer, I want an Alembic migration that adds lifecycle columns to the existing PostgreSQL sessions table, so that the dual-write pattern can track session status and the schema changes are versioned and repeatable.

#### Acceptance Criteria

1. THE Alembic_Migration SHALL add a closed_at (TIMESTAMP WITH TIME ZONE, nullable) column to the sessions table to record when a session ended
2. THE Alembic_Migration SHALL add an updated_at (TIMESTAMP WITH TIME ZONE, nullable, default now()) column to the sessions table to track the last modification time
3. THE Alembic_Migration SHALL add a status (VARCHAR(20), default 'active') column to the sessions table to distinguish active, closed, and archived sessions
4. THE Alembic_Migration SHALL create a composite index on sessions(user_id, created_at DESC) to support efficient session history queries ordered by recency
5. THE Alembic_Migration SHALL be reversible with a downgrade function that removes the added columns and indexes

### Requirement 6: Update Patient Context on PostgreSQL During Session

**User Story:** As a clinician, I want the persistent session record to reflect the latest patient context as I provide more information during the consultation, so that the stored data is always up to date.

#### Acceptance Criteria

1. WHEN the Orchestrator patches the patient_context in Redis after intake extraction, THE Dual_Write_Layer SHALL update the patient_context JSONB column in the PostgreSQL sessions table for the same session_id
2. THE Session_Repository SHALL set the updated_at timestamp to the current UTC time on the sessions row each time the patient_context is modified

### Requirement 7: Frontend Session Detail Page

**User Story:** As a clinician, I want to click on a session in the history list and see the full consultation details (patient context, each turn's query and diagnostic/treatment results, citations), so that I can review past clinical decisions without re-entering the chat.

#### Acceptance Criteria

1. WHEN a clinician navigates to /sessions/{id}, THE frontend SHALL fetch the Session_Detail from the GET /api/sessions/{id} proxy endpoint and render a read-only consultation view
2. THE frontend SHALL display the Patient_Context fields (age, sex, chief complaint, region) at the top of the session detail page
3. THE frontend SHALL render each turn in chronological order showing the clinician query, differential diagnosis items, treatment lines, and citations
4. IF the session detail request returns HTTP 404, THEN THE frontend SHALL display a message indicating the session was not found
5. WHILE the session detail is loading, THE frontend SHALL display a loading skeleton consistent with the existing sessions list page

### Requirement 8: Frontend Session Detail Proxy Route

**User Story:** As a developer, I want a Next.js API proxy route for session detail requests, so that the frontend can fetch individual session data through the authenticated proxy layer.

#### Acceptance Criteria

1. WHEN the frontend sends a GET request to /api/sessions/{id}, THE Frontend_Proxy SHALL forward the request to the Gateway at GET /api/v1/sessions/{id} with the authentication cookie
2. THE Frontend_Proxy SHALL return the Gateway response body and status code to the frontend without modification

### Requirement 9: Data Retention Policy

**User Story:** As a system administrator, I want a configurable retention policy for persistent session data, so that storage costs are managed and data governance requirements are met.

#### Acceptance Criteria

1. THE Session_Repository SHALL read a configurable retention period from the SESSION_RETENTION_DAYS environment variable, defaulting to 365 days when the variable is not set
2. WHEN the Gateway serves the session history list, THE Session_Repository SHALL mark any session with created_at older than the retention period as 'archived' by updating the status column
3. THE Gateway SHALL exclude sessions with status 'archived' from the default GET /api/v1/sessions response
4. WHERE an administrator includes the query parameter include_archived=true, THE Gateway SHALL include archived sessions in the GET /api/v1/sessions response

### Requirement 10: Session Close on Expiry

**User Story:** As a clinician, I want sessions to be marked as closed when they expire from Redis, so that the persistent record accurately reflects the session lifecycle.

#### Acceptance Criteria

1. WHEN a session is found in PostgreSQL with status 'active' but is not found in Redis, THE Dual_Write_Layer SHALL update the session status to 'closed' and set the closed_at timestamp to the current UTC time
2. THE Dual_Write_Layer SHALL perform this status transition lazily during session detail or session list requests rather than requiring a background polling process
