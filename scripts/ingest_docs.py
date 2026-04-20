#!/usr/bin/env python3
"""
Bulk-ingest all PDF/DOCX files from docs/medic/ into the TropiCare knowledge base.

Usage:
    python scripts/ingest_docs.py [--gateway http://localhost:8000]

Authenticates as admin, then uploads each file via POST /api/v1/admin/documents.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "medic"
EXTENSIONS = {".pdf", ".docx"}

ADMIN_EMAIL = "admin@tropicare.health"
ADMIN_PASSWORD = "AdminPass123"

# Map filename keywords to source_type + human-readable title prefix
SOURCE_RULES: list[tuple[list[str], str, str]] = [
    (["came", "lnme", "formulaire", "medicament"],  "formulary",     "CAME Formulary"),
    (["pnlp", "paludisme", "malaria-protocol"],     "epidemiology",  "PNLP Togo"),
    (["amr", "glass", "resistance"],                 "amr_data",      "AMR Data"),
    (["epid", "outbreak", "surveillance"],            "epidemiology",  "Epidemiology"),
]
DEFAULT_SOURCE_TYPE = "guideline"
DEFAULT_TITLE_PREFIX = "WHO Guideline"


def classify(filename: str) -> tuple[str, str]:
    """Return (source_type, title_prefix) based on filename keywords."""
    lower = filename.lower()
    for keywords, src_type, prefix in SOURCE_RULES:
        if any(kw in lower for kw in keywords):
            return src_type, prefix
    return DEFAULT_SOURCE_TYPE, DEFAULT_TITLE_PREFIX


def make_title(path: Path, prefix: str) -> str:
    """Build a human-readable title from filename."""
    stem = path.stem.replace("-", " ").replace("_", " ").title()
    return f"{prefix} — {stem}"


def login(client: httpx.Client, gateway: str) -> str:
    """Authenticate as admin and return the access token."""
    r = client.post(
        f"{gateway}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if r.status_code != 200:
        print(f"Login failed ({r.status_code}): {r.text}", file=sys.stderr)
        sys.exit(1)
    token = r.json()["access_token"]
    print(f"Authenticated as {ADMIN_EMAIL}")
    return token


def upload(client: httpx.Client, gateway: str, token: str, path: Path) -> dict:
    """Upload a single document and return the API response."""
    source_type, prefix = classify(path.name)
    title = make_title(path, prefix)

    with open(path, "rb") as f:
        r = client.post(
            f"{gateway}/api/v1/admin/documents",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (path.name, f, "application/octet-stream")},
            data={
                "title": title,
                "source_type": source_type,
                "version": "2024",
            },
            timeout=120,
        )

    if r.status_code in (201, 202):
        data = r.json()
        print(f"  ✓ {path.name} → {source_type} (doc_id: {data['document_id']})")
        return data
    else:
        print(f"  ✗ {path.name} — {r.status_code}: {r.text}", file=sys.stderr)
        return {}


def main():
    parser = argparse.ArgumentParser(description="Bulk-ingest docs/medic/ into TropiCare KB")
    parser.add_argument("--gateway", default="http://localhost:8000", help="Gateway base URL")
    args = parser.parse_args()

    files = sorted(
        p for p in DOCS_DIR.iterdir()
        if p.suffix.lower() in EXTENSIONS and not p.name.startswith(".")
    )

    if not files:
        print(f"No PDF/DOCX files found in {DOCS_DIR}")
        print("Download the clinical guidelines and place them there first.")
        print("See docs/medic/README.md for the list of expected documents.")
        sys.exit(0)

    print(f"Found {len(files)} document(s) in {DOCS_DIR}\n")

    with httpx.Client() as client:
        token = login(client, args.gateway)
        print()

        ok, fail = 0, 0
        for path in files:
            result = upload(client, args.gateway, token, path)
            if result:
                ok += 1
            else:
                fail += 1

        print(f"\nDone: {ok} uploaded, {fail} failed")


if __name__ == "__main__":
    main()
