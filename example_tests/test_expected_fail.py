# | 18 |              test_xFail               |  expected fail  | 0  | 0  | 1  |  pass   | 0 | 0 | 0 | failure | 0 | 0 | 1 |   pass   | 0 | 0 | 0 | 0.00887  | 0.000443 | 0.00772  | 0.000706 |  xFail  |
# | 19 |           test_xFail_Strict           |  expected fail  | 0  | 0  | 1  |  pass   | 0 | 0 | 0 | failure | 0 | 0 | 1 |   pass   | 0 | 0 | 0 | 0.00954  | 0.000459 | 0.00834  | 0.00074  |  xFail  |
# | 20 |       test_xFail_unexpectedPass       | unexpected pass | 0  | 0  | 0  |  pass   | 0 | 0 | 0 |  pass   | 0 | 0 | 0 |   pass   | 0 | 0 | 0 | 0.00143  | 0.000549 | 0.000501 | 0.00038  |  xPass  |
# | 21 |   test_xFail_unexpectedPass_Strict    |     failure     | 0  | 0  | 1  |  pass   | 0 | 0 | 0 | failure | 0 | 0 | 1 |   pass   | 0 | 0 | 0 | 0.00273  | 0.000468 | 0.00158  | 0.000679 | passed  |
# | 22 |            test_xFail_less            |  expected fail  | 0  | 0  | 1  |  pass   | 0 | 0 | 0 | failure | 0 | 0 | 1 |   pass   | 0 | 0 | 0 | 0.00963  | 0.000457 | 0.00839  | 0.000776 |  xFail  |
# | 23 |          test_xFail_greater           |     failure     | 0  | 0  | 1  |  pass   | 0 | 0 | 0 | failure | 0 | 0 | 1 |   pass   | 0 | 0 | 0 | 0.00931  | 0.000475 | 0.00812  | 0.000719 | passed  |
# | 24 |           test_xFail_during           |  expected fail  | 0  | 0  | 1  |  pass   | 0 | 0 | 0 | failure | 0 | 0 | 1 |   pass   | 0 | 0 | 0 | 0.00279  | 0.000445 | 0.00166  | 0.000687 |  xFail  |


import pytest
import sys
from pytest import (
    log,
    verify
)


# Test outcome: expected fail
@pytest.mark.xfail()
def test_expected_fail():  # xFailed report (strict=False)
    log.high_level_step("----------------------------------------------------")
    log.high_level_step("expected to fail and fails")
    a = 0
    b = 1
    assert a == b, "Expected to fail"


# Test outcome: expected fail
# with strict=True xPass results become failures (not this test)
@pytest.mark.xfail(strict=True)
def test_expected_fail_strict():  # xFailed report (strict=False)
    log.high_level_step("----------------------------------------------------")
    log.high_level_step("expected to fail and fails (strict)")
    a = 0
    b = 1
    assert a == b, "Expected to fail"


# Test outcome: unexpected pass
# xPassed report (strict=False)
@pytest.mark.xfail()
def test_unexpected_pass():
    log.high_level_step("----------------------------------------------------")
    log.high_level_step("expected to fail and unexpectedly passes")
    a = 1
    b = 1
    assert a == b, "Expected to fail but passes"


# Test outcome: failure
# with strict=True xPass results become failures
# xPassed report (strict=False)
@pytest.mark.xfail(strict=True)
def test_unexpected_pass_strict():
    log.high_level_step("----------------------------------------------------")
    log.high_level_step("expected to fail and unexpectedly passes (strict)")
    a = 1
    b = 1
    assert a == b, "Expected to fail but passes"


# Test outcome: expected fail
# If condition is True xFail if test fails
@pytest.mark.xfail(sys.version_info <= (3, 3),
                   reason="expected to fail if version is <= 3.3")
def test_expected_fail_less():
    log.high_level_step("----------------------------------------------------")
    log.high_level_step("expected fail less than with reason")
    log.detail_step("sys.version_info = {}".format(sys.version_info))
    a = 0
    b = 1
    # Test xFails if this asserts, and unexpectedly passes if not (because
    # version is not > 3.3)
    # FIXME if the above comment is on next line it prints in the traceback
    # up to the comma
    assert a == b, "Fail"


# Test outcome: failure (if test function asserts else passes)
# TODO think about changing this result to unexpected pass or be careful in
# the documenting this behaviour as it is different to unexpected pass of a
# type passed
# test function - not sure if this is even possible because the report is
@pytest.mark.xfail(sys.version_info > (3, 3), reason="expected to fail if "
                                                     "version is > 3.3")
def test_expected_fail_greater():
    log.high_level_step("----------------------------------------------------")
    log.high_level_step("expected fail greater than with reason")
    log.detail_step("sys.version_info = {}".format(sys.version_info))
    a = 0
    b = 1
    # Test fails if this asserts, and passes if not (because version is not >
    # 3.3)
    # assert a == b, "Fail"


def test_expected_fail_during():
    pytest.xfail("xfail reason")
