# TropiCare API Reference

Base URL: `http://localhost:8000`

All responses use JSON unless otherwise noted. Authentication uses JWT RS256 Bearer tokens obtained via the login endpoint.

---

## Authentication

### Register

Create a new user account.

```
POST /api/v1/auth/register
```

**Rate limit:** 10/min

**Request body:**

```json
{
  "email": "clinician@example.com",
  "password": "SecurePass123",
  "role": "clinician"
}
```

| Field      | Type   | Required | Description                          |
|------------|--------|----------|--------------------------------------|
| `email`    | string | Yes      | Valid email address                  |
| `password` | string | Yes      | ≥10 chars, 1 uppercase, 1 lowercase, 1 digit |
| `role`     | string | Yes      | `"clinician"` or `"admin"`           |

**Responses:**

| Status | Description                  | Body                                      |
|--------|------------------------------|--------------------------------------------|
| 201    | User created                 | `{ "user_id": "uuid", "email": "..." }`   |
| 409    | Email already registered     | `{ "detail": "Email already registered" }` |
| 422    | Weak password                | `{ "detail": "Password must be ≥10 chars with upper, lower, digit" }` |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dr.kofi@example.com","password":"SecurePass123","role":"clinician"}'
```

---

### Login

Authenticate and receive JWT tokens.

```
POST /api/v1/auth/login
```

**Rate limit:** 10/min

**Request body:**

```json
{
  "email": "clinician@example.com",
  "password": "SecurePass123"
}
```

**Responses:**

| Status | Description              | Body                                                                 |
|--------|--------------------------|----------------------------------------------------------------------|
| 200    | Login successful         | `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }` |
| 401    | Invalid credentials      | `{ "detail": "Invalid credentials" }`                                |
| 423    | Account locked           | `{ "detail": "Account locked — retry in N minutes" }`               |

Account lockout triggers after 5 failed attempts within 30 minutes. Lock duration: 15 minutes.

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dr.kofi@example.com","password":"SecurePass123"}'
```

---

### Refresh Token

Rotate access and refresh tokens.

```
POST /api/v1/auth/refresh
```

**Rate limit:** 10/min

**Request body:**

```json
{
  "refresh_token": "eyJ..."
}
```

**Responses:**

| Status | Description                    | Body                                                    |
|--------|--------------------------------|---------------------------------------------------------|
| 200    | Tokens refreshed               | `{ "access_token": "...", "refresh_token": "..." }`     |
| 401    | Invalid or expired token       | `{ "detail": "Invalid or expired refresh token" }`      |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"eyJ..."}'
```

---

### Get Current User

```
GET /api/v1/auth/me
```

**Auth:** Bearer token required

**Response (200):**

```json
{
  "id": "uuid",
  "email": "dr.kofi@example.com",
  "roles": ["clinician"],
  "active": true
}
```

**Example:**

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJ..."
```

---

## Sessions & Turns

### Create Session

Start a new consultation session.

```
POST /api/v1/sessions
```

**Auth:** Clinician role required
**Rate limit:** 30/min

**Request body:**

```json
{
  "patient_context": {
    "age_years": 34,
    "sex": "F",
    "weight_kg": 62.0,
    "region": "Maritime",
    "chief_complaint": "Fièvre depuis 3 jours avec céphalées",
    "symptoms": [{"text": "fièvre"}, {"text": "céphalées"}],
    "allergies": [],
    "pregnancy_status": "not_applicable",
    "current_medications": [],
    "lab_results": [],
    "travel_history": []
  },
  "language": "fr"
}
```

| Field              | Type   | Required | Description                                    |
|--------------------|--------|----------|------------------------------------------------|
| `patient_context`  | object | No       | Patient context (can be empty, filled by Intake Agent) |
| `language`         | string | No       | `"fr"` (default) or `"en"`                     |

**Responses:**

| Status | Description                    | Body                                          |
|--------|--------------------------------|-----------------------------------------------|
| 201    | Session created                | `{ "session_id": "uuid" }`                    |
| 429    | Too many concurrent sessions   | `{ "detail": "Maximum 5 concurrent sessions" }` |
| 503    | Redis unavailable              | `{ "detail": "Session service temporarily unavailable" }` |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"patient_context":{},"language":"fr"}'
```

---

### Get Session

Retrieve session state.

```
GET /api/v1/sessions/{session_id}
```

**Auth:** Clinician role required

**Responses:**

| Status | Description       | Body                    |
|--------|-------------------|-------------------------|
| 200    | Session found     | Session state object    |
| 404    | Not found         | `{ "detail": "Session not found" }` |

**Example:**

```bash
curl http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer eyJ..."
```

---

### Submit Turn

Submit a clinical query and receive a streaming NDJSON response.

```
POST /api/v1/sessions/{session_id}/turns
```

**Auth:** Clinician role required
**Rate limit:** 60/min
**Response format:** `application/x-ndjson` (one JSON object per line)

**Request body:**

```json
{
  "query": "Patiente de 34 ans avec fièvre depuis 3 jours, céphalées, région Maritime",
  "mode": "auto"
}
```

| Field   | Type   | Required | Description                                          |
|---------|--------|----------|------------------------------------------------------|
| `query` | string | Yes      | Clinical query text (max 5000 chars)                 |
| `mode`  | string | No       | `"auto"` (default), `"diagnostic"`, or `"antibiotherapy"` |

**Responses:**

| Status | Description              | Body                                              |
|--------|--------------------------|---------------------------------------------------|
| 200    | Streaming NDJSON         | One JSON object per line                          |
| 404    | Session expired/missing  | `{ "detail": "Session expired or not found" }`    |
| 503    | Session load failure     | `{ "detail": "Session could not be loaded" }`     |

**NDJSON Event Types:**

| Event Type            | Payload                                          | Phase          |
|-----------------------|--------------------------------------------------|----------------|
| `thinking`            | `{ "content": "..." }`                           | All            |
| `clarifying_question` | `{ "content": "..." }`                           | Intake         |
| `emergency_flag`      | `{ "flag": { "disease", "level", "action" } }`   | Diagnostic     |
| `differential_item`   | `{ "item": DiagnosisItem }`                      | Diagnostic     |
| `treatment_line`      | `{ "tier": "first_line", "drug": DrugRegimen }`  | Antibiotherapy |
| `citation`            | `{ "citation": Citation }`                       | Both           |
| `validation`          | `{ "verdict": "PASS\|WARN\|BLOCK", "annotations": [...] }` | Both |
| `error`               | `{ "message": "..." }`                           | Any            |
| `done`                | `{ "turn_id": "uuid", "partial?": true }`        | Final          |

Note: `emergency_flag` events always precede `differential_item` events.

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/sessions/SESSION_ID/turns \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"query":"Fièvre 39.5°C depuis 3 jours, céphalées, région Maritime","mode":"auto"}' \
  --no-buffer
```

**Example NDJSON output:**

```
{"type":"thinking","content":"Analyzing patient context..."}
{"type":"emergency_flag","flag":{"disease":"Severe malaria","level":"critical","action":"Immediate referral"}}
{"type":"differential_item","item":{"rank":1,"disease_name":"Paludisme grave","icd11_code":"1F40.1","confidence":0.85,...}}
{"type":"differential_item","item":{"rank":2,"disease_name":"Méningite bactérienne","icd11_code":"1D00","confidence":0.45,...}}
{"type":"treatment_line","tier":"first_line","drug":{"drug_name":"Artésunate IV","came_available":true,...}}
{"type":"citation","citation":{"ref_id":1,"source_title":"PNLP Guidelines 2023","section":"Severe Malaria",...}}
{"type":"validation","verdict":"PASS","annotations":[]}
{"type":"done","turn_id":"uuid"}
```

---

### Submit Feedback

Submit clinician feedback on a turn.

```
POST /api/v1/feedback
```

**Auth:** Clinician role required

**Request body:**

```json
{
  "turn_id": "uuid",
  "verdict": "correct",
  "clinician_note": "Diagnosis confirmed by lab results",
  "actual_diagnosis": "Paludisme à P. falciparum"
}
```

| Field              | Type   | Required | Description                                |
|--------------------|--------|----------|--------------------------------------------|
| `turn_id`          | string | Yes      | Turn UUID to provide feedback on           |
| `verdict`          | string | Yes      | `"correct"`, `"partial"`, or `"incorrect"` |
| `clinician_note`   | string | No       | Free-text clinician comment                |
| `actual_diagnosis` | string | No       | Clinician's actual diagnosis               |

**Responses:**

| Status | Description      | Body                        |
|--------|------------------|-----------------------------|
| 201    | Feedback saved   | `{ "status": "accepted" }`  |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"turn_id":"TURN_UUID","verdict":"correct","clinician_note":"Confirmed"}'
```

---

## Admin Endpoints

All admin endpoints require the `admin` role in the JWT.

### List Documents

```
GET /api/v1/admin/documents
```

**Auth:** Admin role required

**Response (200):**

```json
[
  {
    "id": "uuid",
    "title": "PNLP Guidelines 2023",
    "source_type": "guideline",
    "version": "2023",
    "published_date": "2023-06-01",
    "ingested_at": "2024-01-15T10:30:00",
    "chunk_count": 142,
    "superseded": false
  }
]
```

**Example:**

```bash
curl http://localhost:8000/api/v1/admin/documents \
  -H "Authorization: Bearer eyJ..."
```

---

### Upload Document

Upload a PDF/DOCX document for ingestion into the knowledge base.

```
POST /api/v1/admin/documents
```

**Auth:** Admin role required
**Content-Type:** `multipart/form-data`

| Field         | Type   | Required | Description                                          |
|---------------|--------|----------|------------------------------------------------------|
| `file`        | binary | Yes      | PDF or DOCX file                                     |
| `title`       | string | No       | Document title (default: "Untitled")                 |
| `source_type` | string | No       | `guideline`, `formulary`, `amr_data`, `epidemiology` |
| `version`     | string | No       | Version string (e.g. "2023")                         |

**Responses:**

| Status | Description      | Body                                              |
|--------|------------------|---------------------------------------------------|
| 202    | Queued           | `{ "document_id": "uuid", "status": "queued" }`  |
| 400    | No file          | `{ "detail": "No file uploaded" }`                |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/admin/documents \
  -H "Authorization: Bearer eyJ..." \
  -F "file=@pnlp_guidelines_2023.pdf" \
  -F "title=PNLP Guidelines 2023" \
  -F "source_type=guideline" \
  -F "version=2023"
```

---

### Supersede Document

Soft-delete a document by marking it as superseded.

```
DELETE /api/v1/admin/documents/{doc_id}?reason_id={reason_id}
```

**Auth:** Admin role required

| Parameter   | Type   | In    | Description                              |
|-------------|--------|-------|------------------------------------------|
| `doc_id`    | string | path  | Document UUID to supersede               |
| `reason_id` | string | query | UUID of the superseding document         |

**Responses:**

| Status | Description      |
|--------|------------------|
| 204    | Document superseded |

**Example:**

```bash
curl -X DELETE "http://localhost:8000/api/v1/admin/documents/OLD_DOC_ID?reason_id=NEW_DOC_ID" \
  -H "Authorization: Bearer eyJ..."
```

---

### Get Analytics

```
GET /api/v1/admin/analytics
```

**Auth:** Admin role required

**Response (200):**

```json
{
  "total_sessions": 1250,
  "total_turns": 4830,
  "avg_latency_ms": 3200.5,
  "top_diagnoses": [
    {"disease_name": "Paludisme", "count": 320, "avg_confidence": 0.82}
  ],
  "emergency_rate": 0.12,
  "feedback_summary": {"correct": 180, "partial": 45, "incorrect": 12},
  "active_users_24h": 8,
  "cache_hit_rate": 0.65,
  "period_start": "2025-01-01",
  "period_end": "2025-01-31"
}
```

**Example:**

```bash
curl http://localhost:8000/api/v1/admin/analytics \
  -H "Authorization: Bearer eyJ..."
```

---

## Infrastructure Endpoints

### Health Check

```
GET /api/v1/health
```

**Auth:** None

**Response (200):**

```json
{
  "status": "ok",
  "service": "tropicare-gateway"
}
```

---

### Prometheus Metrics

```
GET /metrics
```

**Auth:** None
**Response:** Prometheus text exposition format

Exposed metrics include:
- `tropicare_request_count` — request count by endpoint and status code
- `tropicare_agent_latency_seconds` — agent latency histograms (p50, p95, p99) by agent name
- `tropicare_agent_errors_total` — error count by agent name

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning                                    |
|--------|--------------------------------------------|
| 400    | Bad request (missing/invalid fields)       |
| 401    | Unauthorized (missing/invalid/expired JWT) |
| 403    | Forbidden (insufficient role)              |
| 404    | Resource not found or session expired      |
| 409    | Conflict (e.g. duplicate email)            |
| 422    | Validation error (e.g. weak password)      |
| 423    | Account locked                             |
| 429    | Rate limit exceeded or session limit       |
| 503    | Service temporarily unavailable            |

---

## Security

- All string request fields are limited to 5000 characters
- Region fields are validated against: `Maritime`, `Plateaux`, `Centrale`, `Kara`, `Savanes`
- CSRF protection via double-submit cookie pattern on state-changing endpoints
- Security headers on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy`
- PII fields are SHA-256 hashed before writing to the audit log
