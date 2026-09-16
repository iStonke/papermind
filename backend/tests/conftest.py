"""CI must run the integration/OCR checks instead of silently skipping them."""
import os

import pytest


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("PAPERMIND_REQUIRE_ALL_TESTS") != "1":
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = reporter.stats.get("skipped", []) if reporter else []
    if skipped:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter.write_sep("=", f"CI requires all tests: {len(skipped)} unexpected skips", red=True)
