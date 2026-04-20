@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM start-dev.bat — Start TropiCare local development environment (Windows)
REM ─────────────────────────────────────────────────────────────────────────────
setlocal enabledelayedexpansion

echo.
echo   ╔══════════════════════════════════════╗
echo   ║   TropiCare — Starting local dev     ║
echo   ╚══════════════════════════════════════╝
echo.

REM ── Pre-flight checks ──────────────────────────────────────────────────────
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   [X] Docker is not installed
    exit /b 1
)

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo   [X] Docker daemon is not running
    exit /b 1
)

echo   [OK] Docker is available

REM ── .env file ───────────────────────────────────────────────────────────────
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo   [!] .env created from .env.example
        echo   [!] Please fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
        echo.
        pause
    ) else (
        echo   [X] .env file not found and no .env.example to copy from
        exit /b 1
    )
)

echo   [OK] .env file found

REM ── JWT keys ────────────────────────────────────────────────────────────────
if not exist keys\private.pem (
    echo   [..] Generating RS256 JWT key pair...
    if not exist keys mkdir keys
    openssl genrsa -out keys\private.pem 4096 2>nul
    openssl rsa -in keys\private.pem -pubout -out keys\public.pem 2>nul
    if %errorlevel% neq 0 (
        echo   [X] openssl not found — install OpenSSL or generate keys manually
        exit /b 1
    )
    echo   [OK] JWT keys generated in keys\
) else (
    echo   [OK] JWT keys already exist
)

REM ── Start Docker stack ──────────────────────────────────────────────────────
echo   [..] Starting Docker services...
docker compose up -d --build
if %errorlevel% neq 0 (
    echo   [X] Failed to start Docker services
    exit /b 1
)

REM ── Wait for Gateway health ─────────────────────────────────────────────────
echo   [..] Waiting for services to be healthy...

set retries=30
:wait_gateway
if %retries% leq 0 (
    echo   [!] Gateway did not become healthy in time
    goto :summary
)
curl -sf http://localhost:8000/api/v1/health >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Gateway is ready
    goto :wait_qdrant
)
set /a retries=%retries%-1
timeout /t 2 /nobreak >nul
goto :wait_gateway

:wait_qdrant
set retries=30
:wait_qdrant_loop
if %retries% leq 0 (
    echo   [!] Qdrant did not become healthy in time
    goto :atlas_index
)
curl -sf http://localhost:6333/healthz >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Qdrant is ready
    goto :atlas_index
)
set /a retries=%retries%-1
timeout /t 2 /nobreak >nul
goto :wait_qdrant_loop

REM ── MongoDB Atlas vector search index (if using Atlas) ──────────────────────
:atlas_index
findstr /B "MONGODB_URI=mongodb+srv" .env >nul 2>&1
if %errorlevel% equ 0 (
    echo   [..] MongoDB Atlas detected — ensuring vector search index exists...
    python scripts\setup_atlas_index.py
    if %errorlevel% neq 0 (
        echo   [!] Atlas index setup failed (see output above^)
    )
)

REM ── Ingest knowledge base documents (if any) ───────────────────────────────
:ingest_docs
set DOC_COUNT=0
for %%f in (docs\medic\*.pdf docs\medic\*.docx) do set /a DOC_COUNT+=1
if %DOC_COUNT% gtr 0 (
    echo   [..] Found %DOC_COUNT% document(s^) in docs\medic\ — ingesting into knowledge base...
    python scripts\ingest_docs.py --gateway http://localhost:8000
    if %errorlevel% neq 0 (
        echo   [!] Document ingestion had errors (see output above^)
    )
) else (
    echo   [!] No PDF/DOCX files in docs\medic\ — knowledge base will be empty
    echo   [!] Place clinical guidelines there and re-run, or run: python scripts\ingest_docs.py
)

REM ── Summary ─────────────────────────────────────────────────────────────────
:summary
echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║   TropiCare is running!                          ║
echo   ╠══════════════════════════════════════════════════╣
echo   ║   Frontend   → http://localhost:3000             ║
echo   ║   Gateway    → http://localhost:8000             ║
echo   ║   Grafana    → http://localhost:3001             ║
echo   ║   Jaeger     → http://localhost:16686            ║
echo   ║   Qdrant     → http://localhost:6333             ║
echo   ╠══════════════════════════════════════════════════╣
echo   ║   Stop with: stop-dev.bat                        ║
echo   ║   Logs with: docker compose logs -f gateway      ║
echo   ╚══════════════════════════════════════════════════╝
echo.

endlocal
