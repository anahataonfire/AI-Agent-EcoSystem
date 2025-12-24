"""
Test for version immutability.

Verifies version cannot be overridden by environment.
"""

import pytest
import os


class TestVersionImmutability:
    """Tests for version immutability."""

    def test_version_is_1_0_0(self):
        """Version should be 1.0.0."""
        from src.version import __version__
        assert __version__ == "1.0.0"

    def test_version_info_tuple(self):
        """Version info should be (1, 0, 0)."""
        from src.version import __version_info__
        assert __version_info__ == (1, 0, 0)

    def test_get_version_returns_string(self):
        """get_version should return version string."""
        from src.version import get_version
        assert get_version() == "1.0.0"

    def test_version_not_overridable_by_env(self):
        """Version should not be overridable by environment."""
        # Set env var (would override if checked)
        os.environ["DTL_VERSION"] = "9.9.9"
        
        # Re-import to check
        from src.version import get_version
        
        # Should still be 1.0.0
        assert get_version() == "1.0.0"
        
        # Cleanup
        del os.environ["DTL_VERSION"]

    def test_version_metadata_complete(self):
        """Version metadata should be complete."""
        from src.version import VERSION_METADATA
        
        assert VERSION_METADATA["version"] == "1.0.0"
        assert VERSION_METADATA["autonomy_level"] == "Strategic"
        assert VERSION_METADATA["certification"] == "PASS"
