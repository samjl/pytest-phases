import pytest
from pytest import log


# os module not imported - causes collection error - CollectReport
@pytest.mark.xfail(os.uname()[0] != "Linux",
                   reason="expected to fail if os version is not linux")
def test_collect_error():
    log.highLevelStep("------------------------------------------------------")
    log.highLevelStep("test_xFail - reason")
    a = 0
    b = 1
    # Test fails if this asserts, and passes if not (because os.uname()[1] is
    # linux)
    assert a == b, "Fail"
