import pytest
from pytest import (
    log,
    verify,
    fixture,
    skip
)


# @fixture(scope='module', params=["x", "y"])  # , params=["x", "y"]
# def module_scoped_fix(request):
#     """Module scoped setup and teardown fixture.
#     Autouse applies the fixture to every test function in the module.
#     Local variables added to aid plugin debugging only.
#     :param request: object is used to introspect the "requesting" test
#     function, class or module context.
#     """
#     def module_teardown():
#         log.high_level_step("module_phase_saved_pass-teardown")
#         verify(True, "module_phase_saved_pass-teardown-1:pass")
#     request.addfinalizer(module_teardown)
#
#     def module_setup():
#         log.high_level_step("module_phase_saved_pass-setup")
#         verify(True, "module_phase_saved_pass-setup-1:pass")
#     module_setup()


@fixture(scope='module', params=["x", "y"], autouse=True)
def module_scoped_fix(request):
    """Module scoped setup and teardown fixture.
    Autouse applies the fixture to every test function in the module.
    Local variables added to aid plugin debugging only.
    :param request: object is used to introspect the "requesting" test
    function, class or module context.
    """
    def module_teardown():
        log.high_level_step("module_phase_saved_pass-teardown")
        verify(True, "module_phase_saved_pass-teardown-1:pass")

    def module_setup():
        log.high_level_step("module_phase_saved_pass-setup")
        verify(True, "module_phase_saved_pass-setup-1:pass")

    module_setup()
    yield
    module_teardown()


@fixture(scope='function', params=["a", "b"])
# @fixture(scope='function')
def function_params_fix(request):
    """Function scoped setup and teardown fixture.
    Applied to functions that include it as an argument.
    Local variables added to aid plugin debugging only.
    :param request: object is used to introspect the "requesting" test
    function, class or module context.
    """
    # log.high_level_step("Fixture has params: {}".format(request.param))

    def function_teardown():
        log.high_level_step("function_params_fix-teardown")
        verify(True, "function_params_fix-teardown:pass")
    request.addfinalizer(function_teardown)

    def function_setup():
        log.high_level_step("function_params_fix-setup")
        verify(True, "function_params_fix-setup:pass")
    function_setup()


def test_one(function_params_fix):  # module_scoped_fix
    """Test uses module and function scoped fixtures."""
    log.high_level_step("test_no_fixture")
    verify(True, "test_no_fixture:call-1:pass")


def test_two(function_params_fix):  # module_scoped_fix
    # module_scoped_fix
    """Test uses module scoped fixture only."""
    log.high_level_step("test_func_fixture")
    verify(True, "test_func_fixture:call-1:pass")
