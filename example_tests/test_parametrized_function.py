from pytest import (
    log,
    mark,
    verify,
    fixture
)


@mark.parametrize("a", [0, 1, 2])  # a[0] etc are saved as active_setups
def test_param(a):
    log.high_level_step("Starting test with param a = {}".format(a))
    verify(a > 0, "a fails", warn_condition=a > 1, warn_message="a warns")
