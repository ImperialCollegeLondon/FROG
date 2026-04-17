"""Check that the CITATION.cff file is valid."""

import yaml

from frog.config import APP_VERSION


def test_version() -> None:
    """Check that the version field. matches the package version."""
    with open("CITATION.cff", encoding="utf-8") as f:
        citation_version = yaml.safe_load(f)["version"]

    assert APP_VERSION == citation_version, (
        "version field in CITATION.cff does not match package version"
    )
