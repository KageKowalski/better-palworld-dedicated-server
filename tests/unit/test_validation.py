"""Unit tests for src/validation.py - extracted validation logic."""

import pytest

from src.validation import (
    CorrectionResult,
    PASSWORD_MASK,
    is_password_setting,
    validate_and_correct,
)


class TestIsPasswordSetting:
    """Tests for is_password_setting() helper."""

    def test_admin_password_detected(self):
        assert is_password_setting("AdminPassword") is True

    def test_server_password_detected(self):
        assert is_password_setting("ServerPassword") is True

    def test_non_password_key(self):
        assert is_password_setting("ServerName") is False

    def test_case_sensitive_no_match(self):
        # "password" (lowercase p) should NOT match
        assert is_password_setting("adminpassword") is False

    def test_password_substring_anywhere(self):
        assert is_password_setting("MyPasswordField") is True


class TestPasswordMask:
    """Tests for PASSWORD_MASK constant."""

    def test_mask_value(self):
        assert PASSWORD_MASK == "********"


class TestValidateAndCorrectUnknownKeys:
    """Tests for unknown keys (Requirement 6.9)."""

    def test_unknown_key_returns_value_as_is(self):
        result = validate_and_correct("SomeUnknownSetting", "any_value")
        assert isinstance(result, CorrectionResult)
        assert result.value == "any_value"
        assert result.was_corrected is False
        assert result.original_input == "any_value"

    def test_unknown_key_preserves_special_chars(self):
        result = validate_and_correct("CustomKey", "value with spaces & symbols!")
        assert isinstance(result, CorrectionResult)
        assert result.value == "value with spaces & symbols!"


class TestValidateAndCorrectBoolean:
    """Tests for boolean normalization (Requirement 6.2)."""

    def test_true_lowercase_corrected(self):
        result = validate_and_correct("bIsPvP", "true")
        assert isinstance(result, CorrectionResult)
        assert result.value == "True"
        assert result.was_corrected is True

    def test_false_lowercase_corrected(self):
        result = validate_and_correct("bIsPvP", "false")
        assert isinstance(result, CorrectionResult)
        assert result.value == "False"
        assert result.was_corrected is True

    def test_true_correct_case_not_corrected(self):
        result = validate_and_correct("bIsPvP", "True")
        assert isinstance(result, CorrectionResult)
        assert result.value == "True"
        assert result.was_corrected is False

    def test_false_correct_case_not_corrected(self):
        result = validate_and_correct("bIsPvP", "False")
        assert isinstance(result, CorrectionResult)
        assert result.value == "False"
        assert result.was_corrected is False

    def test_invalid_boolean_returns_error(self):
        result = validate_and_correct("bIsPvP", "maybe")
        assert isinstance(result, str)
        assert "must be a boolean" in result


class TestValidateAndCorrectInteger:
    """Tests for integer validation (Requirement 6.2)."""

    def test_valid_integer_in_range(self):
        result = validate_and_correct("ServerPlayerMaxNum", "16")
        assert isinstance(result, CorrectionResult)
        assert result.value == 16
        assert result.was_corrected is False

    def test_integer_below_minimum(self):
        result = validate_and_correct("ServerPlayerMaxNum", "0")
        assert isinstance(result, str)
        assert "out of range" in result

    def test_integer_above_maximum(self):
        result = validate_and_correct("ServerPlayerMaxNum", "100")
        assert isinstance(result, str)
        assert "out of range" in result

    def test_non_numeric_integer_error(self):
        result = validate_and_correct("ServerPlayerMaxNum", "abc")
        assert isinstance(result, str)
        assert "must be an integer" in result


class TestValidateAndCorrectFloat:
    """Tests for float validation (Requirement 6.2)."""

    def test_valid_float_in_range(self):
        result = validate_and_correct("ExpRate", "2.5")
        assert isinstance(result, CorrectionResult)
        assert result.value == 2.5

    def test_float_below_minimum(self):
        result = validate_and_correct("ExpRate", "0.01")
        assert isinstance(result, str)
        assert "out of range" in result

    def test_float_above_maximum(self):
        result = validate_and_correct("ExpRate", "100.0")
        assert isinstance(result, str)
        assert "out of range" in result

    def test_non_numeric_float_error(self):
        result = validate_and_correct("ExpRate", "not_a_number")
        assert isinstance(result, str)
        assert "must be a float" in result


class TestValidateAndCorrectEnum:
    """Tests for enum validation (Requirement 6.2)."""

    def test_valid_enum_value(self):
        result = validate_and_correct("DeathPenalty", "All")
        assert isinstance(result, CorrectionResult)
        assert result.value == "All"
        assert result.was_corrected is False

    def test_invalid_enum_value(self):
        result = validate_and_correct("DeathPenalty", "Invalid")
        assert isinstance(result, str)
        assert "not valid" in result
        assert "Allowed values" in result


class TestValidateAndCorrectString:
    """Tests for string auto-correction (Requirement 6.2)."""

    def test_quoted_string_stripped(self):
        result = validate_and_correct("ServerName", '"My Server"')
        assert isinstance(result, CorrectionResult)
        assert result.value == "My Server"
        assert result.was_corrected is True

    def test_unquoted_string_passed_as_is(self):
        result = validate_and_correct("ServerName", "My Server")
        assert isinstance(result, CorrectionResult)
        assert result.value == "My Server"
        assert result.was_corrected is False

    def test_empty_quoted_string(self):
        result = validate_and_correct("ServerName", '""')
        assert isinstance(result, CorrectionResult)
        assert result.value == ""
        assert result.was_corrected is True
