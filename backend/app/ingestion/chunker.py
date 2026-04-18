# ─────────────────────────────────────────────────────────────────────────────
# tropicare_ingestion/chunker.py
# Semantic chunking: split RawSections into 512-token chunks with 64-token overlap.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")  # compatible with both OpenAI + Nomic


@dataclass
class Chunk:
    text:        str
    section:     str
    page:        int
    language:    str
    doc_type:    str
    source_path: str
    token_count: int


def chunk_sections(
    sections: list["RawSection"],
    max_tokens:     int = 512,
    overlap_tokens: int = 64,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for sec in sections:
        chunks.extend(_chunk_section(sec, max_tokens, overlap_tokens))
    return chunks


def _chunk_section(sec: "RawSection", max_tokens: int, overlap_tokens: int) -> list[Chunk]:
    sentences = _split_sentences(sec.text, sec.language)
    if not sentences:
        return []

    chunks:  list[Chunk] = []
    current: list[str]   = []
    cur_tokens           = 0
    overlap_buf: list[str] = []

    for sent in sentences:
        sent_tokens = len(_enc.encode(sent))

        # If single sentence exceeds max, hard-split it
        if sent_tokens > max_tokens:
            if current:
                chunks.append(_make_chunk(current, sec))
                overlap_buf = _build_overlap(current, overlap_tokens)
                current, cur_tokens = list(overlap_buf), sum(len(_enc.encode(s)) for s in overlap_buf)
            # Hard-split the long sentence by tokens
            for sub in _hard_split(sent, max_tokens - overlap_tokens):
                chunks.append(_make_chunk([sub], sec))
            continue

        if cur_tokens + sent_tokens > max_tokens:
            if current:
                chunks.append(_make_chunk(current, sec))
            # Start new chunk with overlap
            overlap_buf = _build_overlap(current, overlap_tokens)
            current     = list(overlap_buf) + [sent]
            cur_tokens  = sum(len(_enc.encode(s)) for s in current)
        else:
            current.append(sent)
            cur_tokens += sent_tokens

    if current:
        chunks.append(_make_chunk(current, sec))

    return chunks


def _make_chunk(sentences: list[str], sec: "RawSection") -> Chunk:
    text = " ".join(sentences).strip()
    return Chunk(
        text=text,
        section=sec.section,
        page=sec.page,
        language=sec.language,
        doc_type=sec.doc_type,
        source_path=sec.source_path,
        token_count=len(_enc.encode(text)),
    )


def _split_sentences(text: str, lang: str) -> list[str]:
    """Rule-based sentence splitter (no spaCy dependency)."""
    # Split on '. ', '? ', '! ', '\n\n' while preserving abbreviations
    abbrevs = r"(?<!\bDr)(?<!\bPr)(?<!\bM)(?<!\bMme)(?<!\bNo)(?<!\bvol)(?<!\bpp)"
    pattern = abbrevs + r"(?<=[.!?])\s+"
    sentences = re.split(pattern, text)
    # Also split on double newline (paragraph breaks)
    result: list[str] = []
    for s in sentences:
        for para in s.split("\n\n"):
            cleaned = para.strip()
            if cleaned and len(cleaned) > 10:
                result.append(cleaned)
    return result


def _build_overlap(sentences: list[str], overlap_tokens: int) -> list[str]:
    """Return the trailing sentences that fit within overlap_tokens."""
    overlap: list[str] = []
    tokens  = 0
    for sent in reversed(sentences):
        t = len(_enc.encode(sent))
        if tokens + t > overlap_tokens:
            break
        overlap.insert(0, sent)
        tokens += t
    return overlap


def _hard_split(text: str, max_tokens: int) -> list[str]:
    """Split a very long string into token-bounded pieces."""
    tokens = _enc.encode(text)
    parts  = []
    for i in range(0, len(tokens), max_tokens):
        parts.append(_enc.decode(tokens[i:i + max_tokens]))
    return parts
