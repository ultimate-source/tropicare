# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_session_history_bound.py
#
# Property 12: Session conversation history bounded
# For any session in the SessionStore, after appending a turn, the
# conversation_history list SHALL contain at most 20 entries, with the
# oldest entries discarded first.
#
# **Validates: Requirement 30.2**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    dictionaries,
    integers,
    lists,
    text,
)

from backend.app.orchestrator.session import SessionStore

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=50).filter(lambda s: s.strip() != "")

# Generate a turn dict with arbitrary string keys/values
turn_strategy = dictionaries(
    keys=safe_text,
    values=safe_text,
    min_size=1,
    max_size=5,
)

# Generate existing conversation histories with >20 turns to test truncation
history_strategy = lists(
    turn_strategy,
    min_size=0,
    max_size=50,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_session_store_with_mock(existing_data: dict) -> tuple[SessionStore, MagicMock]:
    """Create a SessionStore with a mocked Redis client.

    Returns the store and a mock that captures the data passed to `set`.
    """
    store = SessionStore.__new__(SessionStore)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(existing_data))

    captured = {}

    async def capture_set(key: str, value: str, ex: int | None = None) -> None:
        captured["key"] = key
        captured["value"] = json.loads(value)
        captured["ex"] = ex

    mock_redis.set = AsyncMock(side_effect=capture_set)
    store._redis = mock_redis

    return store, captured


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    existing_history=history_strategy,
    new_turn=turn_strategy,
)
@settings(max_examples=200, deadline=None)
@pytest.mark.asyncio
async def test_append_turn_bounds_history_to_20(
    existing_history: list[dict],
    new_turn: dict,
) -> None:
    """
    **Validates: Requirement 30.2**

    Property 12a: After appending a turn, conversation_history has at most
    20 entries regardless of how many existed before.
    """
    session_data = {
        "session_id": "test-session",
        "patient_context": {},
        "conversation_history": existing_history,
        "language": "fr",
    }

    store, captured = _make_session_store_with_mock(session_data)
    await store.append_turn("test-session", new_turn)

    stored_history = captured["value"]["conversation_history"]
    assert len(stored_history) <= 20


@pytest.mark.property
@given(
    existing_history=history_strategy,
    new_turn=turn_strategy,
)
@settings(max_examples=200, deadline=None)
@pytest.mark.asyncio
async def test_append_turn_preserves_most_recent(
    existing_history: list[dict],
    new_turn: dict,
) -> None:
    """
    **Validates: Requirement 30.2**

    Property 12b: The most recently appended turn is always present in the
    stored history (it is never truncated away).
    """
    session_data = {
        "session_id": "test-session",
        "patient_context": {},
        "conversation_history": existing_history,
        "language": "fr",
    }

    store, captured = _make_session_store_with_mock(session_data)
    await store.append_turn("test-session", new_turn)

    stored_history = captured["value"]["conversation_history"]
    assert stored_history[-1] == new_turn


@pytest.mark.property
@given(
    existing_history=lists(turn_strategy, min_size=21, max_size=50),
    new_turn=turn_strategy,
)
@settings(max_examples=200, deadline=None)
@pytest.mark.asyncio
async def test_append_turn_discards_oldest_first(
    existing_history: list[dict],
    new_turn: dict,
) -> None:
    """
    **Validates: Requirement 30.2**

    Property 12c: When truncation occurs, the oldest entries are discarded
    first — the stored history is a suffix of the full history.
    """
    session_data = {
        "session_id": "test-session",
        "patient_context": {},
        "conversation_history": existing_history,
        "language": "fr",
    }

    store, captured = _make_session_store_with_mock(session_data)
    await store.append_turn("test-session", new_turn)

    stored_history = captured["value"]["conversation_history"]
    full_history = existing_history + [new_turn]
    expected = full_history[-20:]

    assert stored_history == expected
