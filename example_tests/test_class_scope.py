from pytest import (
    log,
    verify,
    fixture,
    skip
)


@fixture(scope='module', autouse=True)
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


@fixture(scope='class')  # , autouse=True
def class_scoped_fix(request):
    """Module scoped setup and teardown fixture.
    Autouse applies the fixture to every test function in the module.
    Local variables added to aid plugin debugging only.
    :param request: object is used to introspect the "requesting" test
    function, class or module context.
    """
    x = "this is the setup and teardown FIXTURE"

    def teardown():
        z = "this is the TEARDOWN function"
        log.high_level_step("class_scoped_fix-teardown")
        # PASS CONDITION
        verify(True, "class_scoped_fix-teardown-1:pass")
        verify(True, "class_scoped_fix-teardown-2:pass")
        # assert False, "FAILED TEARDOWN"
    request.addfinalizer(teardown)

    def setup():
        y1 = "this is the SETUP function"
        y2 = "another message"
        log.high_level_step("class_scoped_fix-setup")
        # PASS CONDITION
        verify(True, "class_scoped_fix-setup-1:pass")
        verify(True, "class_scoped_fix-setup-2:pass")
        verify(False, "class_scoped_fix-setup:warning", warning=True)
        # assert False
        # abstracted_setup()
    setup()


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
        verify(True, "function_phase_saved_pass-teardown:pass", raise_immediately=False)
    request.addfinalizer(teardown)

    def setup():
        log.high_level_step("function_phase_saved_pass-setup")
        # PASS CONDITION
        verify(True, "function_phase_saved_pass-setup:pass", raise_immediately=False)
        # verify(False, "function_phase_warning-setup:warning", warning=True)
        # assert False
        setup_device_1()
        setup_device_2()
    setup()


def setup_device_1():
    a = 1


def setup_device_2():
    b = 2
    verify(True, "setup_device_2:pass", raise_immediately=False)
    # verify(False, "setup_device_2:fail", raise_immediately=False)
    # assert False, "device 2 setup failed"


@fixture(scope='function')
def function_scoped_fix_2(request):
    """Function scoped setup and teardown fixture.
    Applied to functions that include it as an argument.
    Local variables added to aid plugin debugging only.
    :param request: object is used to introspect the "requesting" test
    function, class or module context.
    """
    def teardown():
        log.high_level_step("function_phase_saved_pass-teardown")
        # PASS CONDITION
        verify(True, "function_phase_saved_pass-teardown:pass", raise_immediately=False)
    request.addfinalizer(teardown)

    def setup():
        log.high_level_step("function_phase_saved_pass-setup")
        # PASS CONDITION
        verify(True, "function_phase_saved_pass-setup:pass", raise_immediately=False)
        # verify(False, "function_phase_warning-setup:warning", warning=True)
        # assert False
    setup()


def test_1_module_scope(function_scoped_fix_1):  # module_scoped_fix
    """Test uses module scoped fixture only."""
    log.high_level_step("test_module_scope_1")
    verify(True, "test_module_scope_1:call-1:pass")
    verify(True, "test_module_scope_1:call-2:pass")


def test_2_module_scope(function_scoped_fix_1, function_scoped_fix_2):
    """Test uses module and function scoped fixtures."""
    log.high_level_step("test_module_scope_2")
    verify(True, "test_module_scope_2:call-1:pass")
    verify(True, "test_module_scope_2:call-2:pass")


class TestClass(object):
    def test_3_class_scope(self, class_scoped_fix):
        log.high_level_step("test_3_class_scope")
        verify(True, "test_3_class_scope:call-1:pass")
        verify(True, "test_3_class_scope:call-2:pass")

    def test_4_class_scope(self, class_scoped_fix):
        log.high_level_step("test_4_class_scope")
        verify(True, "test_4_class_scope:call-1:pass")
        verify(True, "test_4_class_scope:call-2:pass")
