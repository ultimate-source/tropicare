# Implementation Plan: Session Persistence

## Overview

Activate the existing PostgreSQL `sessions` and `turns` tables by introducing a dual-write pattern (Redis + PG), updating gateway routes to read from PG for history, adding a frontend session detail page, and covering correctness with Hypothesis property tests. The implementation proceeds in phases: schema migration → repository → dual-write layer → gateway wiring → frontend → tests.

## Tasks

- [x] 1. Alembic migration 0008 — add lifecycle columns to sessions table
  - [x] 1.1 Create `alembic/versions/0008_session_lifecycle_columns.py`
    - Add `closed_at` TIMESTAMPTZ nullable column
    - Add `updated_at` TIMESTAMPTZ nullable column with DEFAULT now()
    - Add `status` VARCHAR(20) with DEFAULT 'active'
    - Create composite index `ix_sessions_user_created` on `(user_id, created_at DESC)`
    - Create index `ix_sessions_status` on `(status)`
    - Downgrade removes the three columns and both indexes
    - Note: The `migrate` Docker service runs `alembic upgrade head` on startup, so the migration applies automatically on next `docker compose up`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 2. SessionRepository — PostgreSQL CRUD operations
  - [x] 2.1 Create `backend/app/orchestrator/session_repository.py`
    - Implement `SessionRepository` class with `asyncpg.Pool` and `retention_days` constructor params
    - Implement `create_session(session_id, user_id, patient_context, language)` — INSERT into sessions with status='active'
    - Implement `upsert_turn(session_id, turn_id, turn_index, query, response)` — INSERT into turns with ON CONFLICT handling
    - Implement `update_patient_context(session_id, patient_context)` — UPDATE sessions SET patient_context, updated_at=now()
    - Implement `get_session_detail(session_id)` — SELECT session + JOIN turns ORDER BY turn_index ASC
    - Implement `list_sessions(user_id, include_archived, limit, offset)` — SELECT with turn_count and last_query subqueries, ordered by created_at DESC; returns `(list[dict], int)` tuple for pagination
    - Implement `close_session(session_id)` — UPDATE status='closed', closed_at=now()
    - Implement `archive_expired(user_id)` — UPDATE status='archived' for sessions older than retention_days
    - Implement `count_turns(session_id)` — SELECT COUNT from turns
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 3.4, 3.6, 4.2, 4.3, 6.1, 6.2, 9.1, 9.2, 10.1_

  - [x] 2.2 Write property test for SessionRepository — turn response JSONB round-trip
    - **Property 3: Turn response JSONB round-trip**
    - **Validates: Requirements 2.2**

  - [x] 2.3 Write property test for SessionRepository — session list correctness
    - **Property 4: Session list correctness**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 9.3**

  - [x] 2.4 Write property test for SessionRepository — session detail completeness and turn ordering
    - **Property 5: Session detail completeness and turn ordering**
    - **Validates: Requirements 2.4, 4.3**

  - [x] 2.5 Write property test for SessionRepository — retention-based archival
    - **Property 8: Retention-based archival**
    - **Validates: Requirements 9.2**

  - [x] 2.6 Write property test for SessionRepository — user ID foreign key invariant
    - **Property 9: User ID foreign key invariant**
    - **Validates: Requirements 1.3**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. DualWriteSessionStore — wraps Redis + PG with fire-and-forget pattern
  - [x] 4.1 Create `backend/app/orchestrator/dual_write.py`
    - Implement `DualWriteSessionStore` class wrapping `SessionStore` (Redis) and `SessionRepository` (PG)
    - Implement `_fire_and_forget(coro, operation, session_id, **ctx)` helper using `asyncio.create_task` with try/except logging
    - Implement `create(session_id, patient_context, language, user_id)` — Redis blocking write, then fire-and-forget PG create
    - Implement `get(session_id)` — delegate to Redis only
    - Implement `get_or_fallback(session_id)` — try Redis first, on miss fall back to PG; lazy close if PG status is 'active'
    - Implement `patch(session_id, **fields)` — Redis blocking write, then fire-and-forget PG update_patient_context if patient_context in fields
    - Implement `append_turn(session_id, turn)` — Redis blocking write, extract turn_id/query/response, compute turn_index from Redis history length, fire-and-forget PG upsert_turn
    - Delegate `register_session` and `count_user_sessions` to Redis store
    - _Requirements: 1.1, 1.2, 2.1, 2.3, 4.1, 4.2, 6.1, 10.1, 10.2_

  - [x] 4.2 Write property test for DualWriteSessionStore — dual-write data integrity
    - **Property 1: Dual-write data integrity**
    - **Validates: Requirements 1.1, 2.1, 6.1**

  - [x] 4.3 Write property test for DualWriteSessionStore — PostgreSQL failure resilience
    - **Property 2: PostgreSQL failure resilience**
    - **Validates: Requirements 1.2, 2.3**

  - [x] 4.4 Write property test for DualWriteSessionStore — Redis-miss fallback
    - **Property 6: Redis-miss fallback**
    - **Validates: Requirements 4.2**

  - [x] 4.5 Write property test for DualWriteSessionStore — lazy session close
    - **Property 7: Lazy session close**
    - **Validates: Requirements 10.1**

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update gateway config and lifespan
  - [x] 6.1 Add `SESSION_RETENTION_DAYS: int = 365` to `Settings` in `backend/app/gateway/config.py`
    - _Requirements: 9.1_

  - [x] 6.2 Update `backend/app/gateway/main.py` lifespan to wire `DualWriteSessionStore`
    - Import `SessionRepository` and `DualWriteSessionStore`
    - Create `SessionRepository(pg_pool, settings.SESSION_RETENTION_DAYS)` during startup
    - Create `DualWriteSessionStore(session_store, session_repo)` during startup
    - Store `session_repo` on `app.state` for direct use by list route
    - Pass `DualWriteSessionStore` as the `session_store` to `OrchestratorConfig`
    - Add `get_repo` dependency function returning `request.app.state.session_repo`
    - _Requirements: 1.1, 2.1, 9.1_

- [x] 7. Update gateway routes
  - [x] 7.1 Update `POST /api/v1/sessions` in `backend/app/gateway/main.py`
    - Pass `user_id` from auth dependency to `DualWriteSessionStore.create()`
    - _Requirements: 1.1, 1.3_

  - [x] 7.2 Update `GET /api/v1/sessions` in `backend/app/gateway/main.py`
    - Change to read from `SessionRepository.list_sessions()` directly
    - Accept optional `include_archived`, `limit`, `offset` query parameters
    - Call `archive_expired(user_id)` for retention-based archival
    - For each returned session with status 'active', check Redis existence and lazy close if absent
    - Return paginated response with `sessions`, `total`, `limit`, `offset`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 9.2, 9.3, 9.4, 10.1, 10.2_

  - [x] 7.3 Update `GET /api/v1/sessions/{session_id}` in `backend/app/gateway/main.py`
    - Use `DualWriteSessionStore.get_or_fallback()` instead of Redis-only `get()`
    - Return 404 if not found in either store, 503 on PG failure after Redis miss
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 7.4 Write unit tests for gateway routes
    - Test create session passes user_id
    - Test list sessions reads from PG, excludes archived by default, includes with query param
    - Test detail endpoint tries Redis first, falls back to PG, returns 404 when both miss
    - Test lazy close triggered on list and detail
    - _Requirements: 1.3, 3.1, 4.1, 4.4, 9.4_

- [x] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Frontend proxy route and API client
  - [x] 9.1 Create `frontend/src/app/api/sessions/[id]/route.ts`
    - Implement GET handler forwarding to `GET /api/v1/sessions/{id}` on the gateway with auth cookie
    - Follow same pattern as existing `frontend/src/app/api/sessions/route.ts`
    - _Requirements: 8.1, 8.2_

  - [x] 9.2 Update `frontend/src/lib/api.ts` — add session detail method
    - Update `sessions.get(id)` return type to a proper `SessionDetail` interface
    - Add `SessionDetail` and `TurnRecord` interfaces to the types section
    - _Requirements: 7.1_

- [x] 10. Frontend session detail page
  - [x] 10.1 Replace `frontend/src/app/(clinic)/sessions/[id]/page.tsx`
    - Convert from server-side redirect to `"use client"` component
    - Fetch `GET /api/sessions/{id}` via `api.sessions.get(id)` using `useEffect` + `useState`
    - Render patient context header (age, sex, chief complaint, region)
    - Render chronological turn list with query, differential items, treatment lines, citations
    - Handle 404 with user-friendly message
    - Show `SkeletonCard` loading skeleton during fetch
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 10.2 Update `frontend/src/app/(clinic)/sessions/page.tsx` for paginated response
    - Update to handle new response shape with `sessions`, `total`, `limit`, `offset` fields
    - Destructure `sessions` from the paginated response instead of assuming flat `{ sessions: [...] }`
    - _Requirements: 3.6_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation between major phases
- Property tests validate universal correctness properties from the design document using Hypothesis (backend) with `@settings(max_examples=100)`
- Unit tests validate specific examples and edge cases using pytest
- The `DualWriteSessionStore` is a drop-in replacement for `SessionStore` — the Orchestrator class itself requires no changes
