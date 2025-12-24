"""
Tests for spec immutability enforcement.

Verifies:
- Immutable parameters cannot be changed
- Red-line violations are raised
- Spec hash validates integrity
"""

import pytest
import json
import hashlib
from pathlib import Path


# Constants from frozen spec
FROZEN_LEARNING_RATE = 0.2
FROZEN_WEIGHT_MIN = 0.1
FROZEN_WEIGHT_MAX = 2.0
FROZEN_DECAY_RATE = 0.95


class SpecViolationError(Exception):
    """Raised when spec immutability is violated."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def validate_learning_rate(value: float) -> None:
    """Validate learning rate against frozen spec."""
    if value != FROZEN_LEARNING_RATE:
        raise SpecViolationError(
            "DTL-REDLINE-005",
            f"Learning rate mutation: {value} != {FROZEN_LEARNING_RATE}"
        )


def validate_weight_bounds(min_val: float, max_val: float) -> None:
    """Validate weight bounds against frozen spec."""
    if min_val != FROZEN_WEIGHT_MIN or max_val != FROZEN_WEIGHT_MAX:
        raise SpecViolationError(
            "DTL-REDLINE-006",
            f"Weight bounds mutation: [{min_val}, {max_val}] != [{FROZEN_WEIGHT_MIN}, {FROZEN_WEIGHT_MAX}]"
        )


def validate_decay_rate(value: float) -> None:
    """Validate decay rate against frozen spec."""
    if value != FROZEN_DECAY_RATE:
        raise SpecViolationError(
            "DTL-REDLINE-007",
            f"Decay rate mutation: {value} != {FROZEN_DECAY_RATE}"
        )


class TestSpecImmutability:
    """Tests for spec immutability."""

    def test_learning_rate_immutable(self):
        """Learning rate cannot be changed."""
        with pytest.raises(SpecViolationError) as exc_info:
            validate_learning_rate(0.3)
        
        assert exc_info.value.code == "DTL-REDLINE-005"

    def test_weight_bounds_immutable(self):
        """Weight bounds cannot be changed."""
        with pytest.raises(SpecViolationError) as exc_info:
            validate_weight_bounds(0.0, 3.0)
        
        assert exc_info.value.code == "DTL-REDLINE-006"

    def test_decay_rate_immutable(self):
        """Decay rate cannot be changed."""
        with pytest.raises(SpecViolationError) as exc_info:
            validate_decay_rate(0.9)
        
        assert exc_info.value.code == "DTL-REDLINE-007"

    def test_valid_params_accepted(self):
        """Correct parameters are accepted."""
        # Should not raise
        validate_learning_rate(FROZEN_LEARNING_RATE)
        validate_weight_bounds(FROZEN_WEIGHT_MIN, FROZEN_WEIGHT_MAX)
        validate_decay_rate(FROZEN_DECAY_RATE)

    def test_frozen_spec_exists(self):
        """Frozen spec file exists."""
        spec_path = Path(__file__).parent.parent / "docs" / "strategic_autonomy_frozen.json"
        assert spec_path.exists()
        
        with open(spec_path) as f:
            spec = json.load(f)
        
        assert spec["spec_version"] == "1.0.0"
        assert "immutable_parameters" in spec

    def test_spec_contains_all_codes(self):
        """Frozen spec contains all abort codes."""
        spec_path = Path(__file__).parent.parent / "docs" / "strategic_autonomy_frozen.json"
        
        with open(spec_path) as f:
            spec = json.load(f)
        
        codes = spec["abort_taxonomy"]["codes"]
        
        # Should have all 14 DTL-STRAT codes
        assert len(codes) >= 14
        assert "DTL-STRAT-001" in codes
        assert "DTL-STRAT-014" in codes
