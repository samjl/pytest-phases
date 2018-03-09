from pytest import (
    log,
    verify,
    fixture,
    skip
)


@fixture(scope='module')  #, autouse=True
def module_scoped_fix(request):
    """Module scoped setup and teardown fixture.
    Autouse applies the fixture to every test function in the module.
    Local variables added to aid plugin debugging only.
    :param request: object is used to introspect the "requesting" test
    function, class or module context.
    """
    x = "this is the setup and teardown FIXTURE"

    def teardown():
        z = "this is the TEARDOWN function"
        log.high_level_step("module_phase_saved_pass-teardown")
        # PASS CONDITION
        verify(True, "module_phase_saved_pass-teardown-1:pass")
        verify(True, "module_phase_saved_pass-teardown-2:pass")
        # assert False, "FAILED TEARDOWN"
    request.addfinalizer(teardown)

    def setup():
        y1 = "this is the SETUP function"
        y2 = "another message"
        log.high_level_step("module_phase_saved_pass-setup")
        # PASS CONDITION
        verify(True, "module_phase_saved_pass-setup-1:pass")
        verify(True, "module_phase_saved_pass-setup-2:pass")
        # verify(False, "module_phase_warning-setup:warning", warning=True)
        # assert False
        # abstracted_setup()
    setup()


# params keys: (w)arning,
#              verify fail and (s)ave,
#              verify fail and raise (i)mmediately,
#              regular (a)ssert
@fixture(scope='function',
         params=[
                 {"w": False, "s": False, "i": False, "a": False},
                 {"w": False, "s": False, "i": False, "a": True},
                 {"w": False, "s": False, "i": True, "a": False},
                 {"w": False, "s": False, "i": True, "a": True},
                 {"w": False, "s": True, "i": False, "a": False},
                 {"w": False, "s": True, "i": False, "a": True},
                 {"w": False, "s": True, "i": True, "a": False},
                 {"w": False, "s": True, "i": True, "a": True},
                 {"w": True, "s": False, "i": False, "a": False},
                 {"w": True, "s": False, "i": False, "a": True},
                 {"w": True, "s": False, "i": True, "a": False},
                 {"w": True, "s": False, "i": True, "a": True},
                 {"w": True, "s": True, "i": False, "a": False},
                 {"w": True, "s": True, "i": False, "a": True},
                 {"w": True, "s": True, "i": True, "a": False},
                 {"w": True, "s": True, "i": True, "a": True}
                 ])
def function_scoped_fix(request):
    """Function scoped setup and teardown fixture.
    Applied to functions that include it as an argument.
    Local variables added to aid plugin debugging only.
    :param request: object is used to introspect the "requesting" test
    function, class or module context.
    """
    log.high_level_step("Fixture has params: {}".format(request.param))

    def teardown():
        log.high_level_step("function_phase_saved_pass-teardown")
        # PASS CONDITION
        verify(True, "function_phase_saved_pass-teardown:pass",
               raise_immediately=False)
    request.addfinalizer(teardown)

    def setup():
        log.high_level_step("function_phase_saved_pass-setup")
        if request.param["w"]:
            verify(False, "setup warning", warning=True)
        if request.param["s"]:
            verify(False, "setup failed verification (saved)",
                   raise_immediately=False)
        if request.param["i"]:
            verify(False, "setup failed verification (raise immediately)")
        if request.param["a"]:
            assert False, "setup regular assertion"
        # else setup has passed
        verify(True, "function_phase_saved_pass-setup passed")
        # log.high_level_step("setup passed")

    setup()


def setup_device_1():
    a = 1


def setup_device_2():
    b = 2
    # verify(False, "setup_device_2:fail", raise_immediately=False)
    # assert False, "device 2 setup failed"


# def test_1_module_scope(module_scoped_fix, function_scoped_fix):  #
#     # module_scoped_fix
#     """Test uses module scoped fixture only."""
#     log.high_level_step("test_module_scope_1")
#     verify(True, "test_module_scope_1:call-1:pass")
#     verify(True, "test_module_scope_1:call-2:pass")


def test_2_module_scope(function_scoped_fix):
    """Test uses module and function scoped fixtures."""
    log.high_level_step("test_module_scope_2")
    verify(True, "test_module_scope_2:call-1:pass")
    verify(True, "test_module_scope_2:call-2:pass")
