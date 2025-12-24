"""
DTL Strategic Autonomy Version.

This version is IMMUTABLE. Do not modify.
"""

# Immutable version - no env override
__version__ = "1.0.0"
__version_info__ = (1, 0, 0)

# Version metadata
VERSION_METADATA = {
    "name": "DTL Strategic Autonomy",
    "version": __version__,
    "codename": "Certified PASS",
    "release_date": "2025-12-23",
    "autonomy_level": "Strategic",
    "certification": "PASS"
}


def get_version() -> str:
    """Return immutable version string."""
    return __version__


def get_version_info() -> tuple:
    """Return immutable version tuple."""
    return __version_info__
