import pytest
from pytest import log


# prints reason if present, otherwise condition
# skips @ setup phase
@pytest.mark.skipif("True", reason="skipping test message")
def test_skip():
    log.high_level_step("This should not be printed")


# skips @ call phase
def test_skip_during():
    log.high_level_step("This should be printed")
    # This is raised as Skipped exception (_pytest/runner.py)
    pytest.skip("skip during test")
    log.high_level_step("This should not be printed")
