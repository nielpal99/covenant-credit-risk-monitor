from pathlib import Path

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires the generated local SEC corpus")


def pytest_collection_modifyitems(config, items):
    if Path("data/AMZN/report.json").is_file():
        return
    skip = pytest.mark.skip(reason="requires the private generated Amazon corpus; run the public suite with pytest -m 'not integration'")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
