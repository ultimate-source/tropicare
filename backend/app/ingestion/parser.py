# ─────────────────────────────────────────────────────────────────────────────
# tropicare_ingestion/parser.py
# Parses PDF, DOCX, and JSON into a list of RawSection objects.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("tropicare.ingestion.parser")


@dataclass
class RawSection:
    text:        str
    section:     str        # heading path, e.g. "Chapitre 4 > 4.2 Traitement"
    page:        int
    language:    str        # "fr" | "en"
    doc_type:    str        # "pdf" | "docx" | "json"
    source_path: str


def parse(path: str | Path) -> list[RawSection]:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(p)
    elif suffix in (".docx", ".doc"):
        return _parse_docx(p)
    elif suffix == ".json":
        return _parse_json(p)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


# ── PDF ───────────────────────────────────────────────────────────────────────

def _parse_pdf(path: Path) -> list[RawSection]:
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    sections: list[RawSection] = []
    current_heading = "Introduction"
    heading_pattern = re.compile(
        r"^(\d+(\.\d+)*\.?\s+[A-ZÀ-Ü].{2,60})$", re.MULTILINE
    )

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text", sort=True)
        if not text.strip():
            continue

        # Detect headings and split into sub-sections
        parts = heading_pattern.split(text)
        # parts alternates: [pre-heading text, heading, subgroup, ...]
        # Simpler: just detect headings to update current_heading
        lines = text.splitlines()
        block_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if heading_pattern.match(stripped) and len(stripped) < 80:
                # Flush current block
                if block_lines:
                    block_text = "\n".join(block_lines).strip()
                    if block_text:
                        sections.append(RawSection(
                            text=block_text,
                            section=current_heading,
                            page=page_num,
                            language=_detect_language(block_text),
                            doc_type="pdf",
                            source_path=str(path),
                        ))
                    block_lines = []
                current_heading = stripped[:80]
            else:
                block_lines.append(line)

        # Flush last block of page
        if block_lines:
            block_text = "\n".join(block_lines).strip()
            if block_text:
                sections.append(RawSection(
                    text=block_text,
                    section=current_heading,
                    page=page_num,
                    language=_detect_language(block_text),
                    doc_type="pdf",
                    source_path=str(path),
                ))

    doc.close()
    log.info("Parsed %s: %d sections across %d pages", path.name, len(sections), page_num)
    return sections


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _parse_docx(path: Path) -> list[RawSection]:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document(str(path))
    sections: list[RawSection] = []
    current_heading = "Introduction"
    buffer: list[str] = []
    page_estimate = 1

    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue

        # Headings by style name
        is_heading = (
            para.style.name.startswith("Heading")
            or para.style.name.startswith("Titre")
        )

        if is_heading:
            if buffer:
                sections.append(RawSection(
                    text="\n".join(buffer),
                    section=current_heading,
                    page=page_estimate,
                    language=_detect_language("\n".join(buffer)),
                    doc_type="docx",
                    source_path=str(path),
                ))
                buffer = []
            current_heading = text[:80]
            page_estimate = max(1, i // 30)  # rough estimate
        else:
            buffer.append(text)
            if i % 30 == 0:  # new page estimate every ~30 paragraphs
                page_estimate += 1

    if buffer:
        sections.append(RawSection(
            text="\n".join(buffer),
            section=current_heading,
            page=page_estimate,
            language=_detect_language("\n".join(buffer)),
            doc_type="docx",
            source_path=str(path),
        ))

    log.info("Parsed %s: %d sections", path.name, len(sections))
    return sections


# ── JSON (structured knowledge: CAME formulary, AMR data) ────────────────────

def _parse_json(path: Path) -> list[RawSection]:
    data = json.loads(path.read_text())
    sections: list[RawSection] = []

    if isinstance(data, list):
        for i, item in enumerate(data):
            text = json.dumps(item, ensure_ascii=False, indent=2)
            sections.append(RawSection(
                text=text,
                section=item.get("category", f"Record {i}"),
                page=i + 1,
                language="fr",
                doc_type="json",
                source_path=str(path),
            ))
    elif isinstance(data, dict):
        for key, val in data.items():
            text = f"{key}:\n{json.dumps(val, ensure_ascii=False, indent=2)}"
            sections.append(RawSection(
                text=text,
                section=key,
                page=1,
                language="fr",
                doc_type="json",
                source_path=str(path),
            ))

    log.info("Parsed JSON %s: %d records", path.name, len(sections))
    return sections


def _detect_language(text: str) -> str:
    fr_markers = ["le ", "la ", "les ", "du ", "des ", "un ", "une ", "est ", "dans "]
    en_markers = ["the ", "and ", "for ", "with ", "this ", "that ", "from "]
    txt = text[:500].lower()
    fr_score = sum(txt.count(m) for m in fr_markers)
    en_score = sum(txt.count(m) for m in en_markers)
    return "fr" if fr_score >= en_score else "en"

