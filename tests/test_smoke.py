"""Phase 0 smoke test — confirms the skeleton imports and the package is on the path.

Keeps `pytest` green on a clean skeleton so the Phase 0 gate (scaffolding builds,
test runner passes) is verifiable before any real code lands.
"""

import novacrm_agent
from novacrm_agent import config


def test_package_imports():
    assert novacrm_agent.__version__ == "0.1.0"


def test_config_has_primary_model():
    assert config.PRIMARY_MODEL
    assert config.PRIMARY_BASE_URL.startswith("https://")
