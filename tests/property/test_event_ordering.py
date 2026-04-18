# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_event_ordering.py
#
# Property 3: Emergency flag ordering invariant
# For all streaming event sequences produced by the Orchestrator, the
# emergency_flag events SHALL precede all differential_item events in
# emission order.
#
# **Validates: Requirements 7.4, 17.8**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    dictionaries,
    fixed_dictionaries,
    just,
    lists,
    one_of,
    sampled_from,
    text,
)

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.orchestrator.orchestrator import order_events

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=50).filter(lambda s: s.strip() != "")

# Generate emergency_flag events
emergency_flag_events = fixed_dictionaries({
    "type": just("emergency_flag"),
    "flag": fixed_dictionaries({
        "disease": safe_text,
        "level": sampled_from(["critical", "urgent"]),
        "action": safe_text,
    }),
})

# Generate differential_item events
differential_item_events = fixed_dictionaries({
    "type": just("differential_item"),
    "item": fixed_dictionaries({
        "rank": sampled_from([1, 2, 3, 4, 5]),
        "disease_name": safe_text,
        "icd11_code": safe_text,
        "confidence": sampled_from([0.1, 0.3, 0.5, 0.7, 0.9]),
    }),
})

# Generate other event types (thinking, citation, treatment_line, etc.)
other_events = fixed_dictionaries({
    "type": sampled_from([
        "thinking", "citation", "treatment_line", "validation", "done",
    ]),
    "content": safe_text,
})

# Mixed list of all event types
mixed_events = lists(
    one_of(emergency_flag_events, differential_item_events, other_events),
    min_size=0,
    max_size=20,
)


# ── Property test ────────────────────────────────────────────────────────────


@pytest.mark.property
@given(events=mixed_events)
@settings(max_examples=200, deadline=None)
def test_emergency_flags_precede_differential_items(events: list[dict]) -> None:
    """
    **Validates: Requirements 7.4, 17.8**

    Property 3: Emergency flag ordering invariant.
    After passing through order_events, every emergency_flag event SHALL
    have a lower index than every differential_item event.
    """
    ordered = order_events(events)

    # Collect indices of emergency_flag and differential_item events
    emergency_indices = [
        i for i, ev in enumerate(ordered) if ev.get("type") == "emergency_flag"
    ]
    differential_indices = [
        i for i, ev in enumerate(ordered) if ev.get("type") == "differential_item"
    ]

    # If both types are present, max emergency index < min differential index
    if emergency_indices and differential_indices:
        max_emergency = max(emergency_indices)
        min_differential = min(differential_indices)
        assert max_emergency < min_differential, (
            f"Emergency flag at index {max_emergency} does not precede "
            f"differential item at index {min_differential}.\n"
            f"Ordered events: {[ev.get('type') for ev in ordered]}"
        )

    # All original events should be preserved (no loss)
    assert len(ordered) == len(events), (
        f"Event count changed: input={len(events)}, output={len(ordered)}"
    )

    # All original emergency_flag events should still be present
    input_emergency_count = sum(
        1 for ev in events if ev.get("type") == "emergency_flag"
    )
    output_emergency_count = len(emergency_indices)
    assert input_emergency_count == output_emergency_count, (
        f"Emergency flag count changed: input={input_emergency_count}, "
        f"output={output_emergency_count}"
    )

    # All original differential_item events should still be present
    input_diff_count = sum(
        1 for ev in events if ev.get("type") == "differential_item"
    )
    output_diff_count = len(differential_indices)
    assert input_diff_count == output_diff_count, (
        f"Differential item count changed: input={input_diff_count}, "
        f"output={output_diff_count}"
    )
