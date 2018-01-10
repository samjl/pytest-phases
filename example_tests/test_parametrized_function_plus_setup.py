from pytest import (
    log,
    mark,
    verify,
    fixture
)

# Check parametrized test functions interaction with setup/teardown fixtures


@fixture(scope='function')
def function_scoped_fix_1(request):
    """Function scoped setup and teardown fixture.
    Applied to functions that include it as an argument.
    Local variables added to aid plugin debugging only.
    :param request: object is used to introspect the "requesting" test
    function, class or module context.
    """
    def teardown():
        log.high_level_step("function_phase_saved_pass-teardown")
        # PASS CONDITION
        verify(True, "function_phase_saved_pass-teardown:pass",
               raise_immediately=False)
    request.addfinalizer(teardown)

    def setup():
        log.high_level_step("function_phase_saved_pass-setup")
        # PASS CONDITION
        verify(True, "function_phase_saved_pass-setup:pass",
               raise_immediately=False)
    setup()


@mark.parametrize("a", [0, 1, 2])  # a[0] etc are saved as active_setups
# fixture and param can be in any order as in both definitions below
def test_param(a, function_scoped_fix_1):
# def test_param(function_scoped_fix_1, a):
    log.high_level_step("Starting test with param a = {}".format(a))
    verify(a > 0, "a fails", warn_condition=a > 1, warn_message="a warns")
