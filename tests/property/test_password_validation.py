# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_password_validation.py
#
# Property 8: Password validation rejects weak passwords
# For any password string that is shorter than 10 characters, or lacks an
# uppercase letter, or lacks a lowercase letter, or lacks a digit, the
# registration endpoint SHALL reject the request with a validation error.
#
# **Validates: Requirement 13.3**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import string
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis.strategies import (
    composite,
    integers,
    sampled_from,
    text,
)

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.gateway.routers.auth import _validate_password

# ── Character sets ───────────────────────────────────────────────────────────

LOWERCASE = string.ascii_lowercase
UPPERCASE = string.ascii_uppercase
DIGITS = string.digits
ALL_VALID = LOWERCASE + UPPERCASE + DIGITS


# ── Strategies ───────────────────────────────────────────────────────────────


@composite
def password_too_short(draw):
    """Generate passwords of length 0–9 with any mix of valid characters."""
    length = draw(integers(min_value=0, max_value=9))
    return draw(text(alphabet=ALL_VALID, min_size=length, max_size=length))


@composite
def password_no_uppercase(draw):
    """Generate passwords ≥10 chars containing only lowercase + digits (no uppercase)."""
    alphabet = LOWERCASE + DIGITS
    return draw(text(alphabet=alphabet, min_size=10, max_size=30).filter(
        lambda s: any(c in LOWERCASE for c in s) and any(c in DIGITS for c in s)
    ))


@composite
def password_no_lowercase(draw):
    """Generate passwords ≥10 chars containing only uppercase + digits (no lowercase)."""
    alphabet = UPPERCASE + DIGITS
    return draw(text(alphabet=alphabet, min_size=10, max_size=30).filter(
        lambda s: any(c in UPPERCASE for c in s) and any(c in DIGITS for c in s)
    ))


@composite
def password_no_digit(draw):
    """Generate passwords ≥10 chars containing only uppercase + lowercase (no digits)."""
    alphabet = UPPERCASE + LOWERCASE
    return draw(text(alphabet=alphabet, min_size=10, max_size=30).filter(
        lambda s: any(c in UPPERCASE for c in s) and any(c in LOWERCASE for c in s)
    ))


@composite
def valid_password(draw):
    """Generate passwords ≥10 chars with at least one uppercase, one lowercase, and one digit."""
    # Guarantee at least one of each required class
    upper = draw(sampled_from(list(UPPERCASE)))
    lower = draw(sampled_from(list(LOWERCASE)))
    digit = draw(sampled_from(list(DIGITS)))
    # Fill remaining length with any valid characters
    remaining = draw(text(alphabet=ALL_VALID, min_size=7, max_size=27))
    # Combine and return (order doesn't matter for validation)
    return upper + lower + digit + remaining


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(pw=password_too_short())
@settings(max_examples=200, deadline=None)
def test_too_short_passwords_rejected(pw: str) -> None:
    """
    **Validates: Requirement 13.3**

    Property 8a: Passwords shorter than 10 characters are rejected.
    """
    with pytest.raises(HTTPException) as exc_info:
        _validate_password(pw)
    assert exc_info.value.status_code == 422


@pytest.mark.property
@given(pw=password_no_uppercase())
@settings(max_examples=200, deadline=None)
def test_no_uppercase_passwords_rejected(pw: str) -> None:
    """
    **Validates: Requirement 13.3**

    Property 8b: Passwords without uppercase letters are rejected.
    """
    with pytest.raises(HTTPException) as exc_info:
        _validate_password(pw)
    assert exc_info.value.status_code == 422


@pytest.mark.property
@given(pw=password_no_lowercase())
@settings(max_examples=200, deadline=None)
def test_no_lowercase_passwords_rejected(pw: str) -> None:
    """
    **Validates: Requirement 13.3**

    Property 8c: Passwords without lowercase letters are rejected.
    """
    with pytest.raises(HTTPException) as exc_info:
        _validate_password(pw)
    assert exc_info.value.status_code == 422


@pytest.mark.property
@given(pw=password_no_digit())
@settings(max_examples=200, deadline=None)
def test_no_digit_passwords_rejected(pw: str) -> None:
    """
    **Validates: Requirement 13.3**

    Property 8d: Passwords without digits are rejected.
    """
    with pytest.raises(HTTPException) as exc_info:
        _validate_password(pw)
    assert exc_info.value.status_code == 422


@pytest.mark.property
@given(pw=valid_password())
@settings(max_examples=200, deadline=None)
def test_valid_passwords_accepted(pw: str) -> None:
    """
    **Validates: Requirement 13.3**

    Property 8e: Passwords meeting all criteria are accepted (no exception raised).
    """
    # Should not raise any exception
    _validate_password(pw)
