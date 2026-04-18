"""Unit tests for user registration endpoint and password validation."""
from __future__ import annotations

import re
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.gateway.routers.auth import _validate_password


# ── _validate_password tests ──────────────────────────────────────────────────


class TestValidatePassword:
    """Tests for the _validate_password helper."""

    def test_valid_password(self):
        """Strong password should not raise."""
        _validate_password("Abcdefgh1x")  # 10 chars, upper, lower, digit

    def test_too_short(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_password("Abc1xxxxx")  # 9 chars
        assert exc_info.value.status_code == 422

    def test_no_uppercase(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_password("abcdefgh1x")
        assert exc_info.value.status_code == 422

    def test_no_lowercase(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_password("ABCDEFGH1X")
        assert exc_info.value.status_code == 422

    def test_no_digit(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_password("Abcdefghxx")
        assert exc_info.value.status_code == 422

    def test_empty_string(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_password("")
        assert exc_info.value.status_code == 422

    def test_exactly_10_chars_valid(self):
        """Boundary: exactly 10 chars with all requirements met."""
        _validate_password("Abcdefgh1x")

    def test_long_valid_password(self):
        """Long password meeting all criteria should pass."""
        _validate_password("A" + "b" * 50 + "1")
