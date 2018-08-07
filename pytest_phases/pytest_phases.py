##
# @file pytest_phases.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin - pytest hooks
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
import os
import pkg_resources
import pytest
import sys
import time
import traceback
from builtins import hex, str
try:
    # Python 3 - module name changed for PEP8 compliance
    from configparser import ConfigParser
except ImportError:
    # Python 2
    from ConfigParser import SafeConfigParser as ConfigParser
from collections import OrderedDict
from future.utils import raise_
from future import standard_library
from past.utils import old_div
from _pytest.fixtures import FixtureDef  # requires pytest version>=3.0.0
from _pytest.python import (
    Class,
    Module
)
from _pytest.runner import CollectReport
from _pytest.skipping import (
    show_skipped,
    show_xfailed,
    show_xpassed
)
from _pytest.terminal import WarningReport
from .common import (
    CONFIG,
    DEBUG,
    debug_print
)
from .loglevels import (
    LogLevel,
    get_current_index
)
from .mongo import MongoConnector
from .outcomes import (
    Outcomes,
    plural,
    outcome_conditions,
    phase_specific_result,
    hierarchy
)
from .outputredirect import LogOutputRedirection  # FIXME replace with get
from .verify import (
    VerificationException,
    WarningException,
    Verifications,
    FailureTraceback,
    Result,
    perform_verification,
    set_saved_raised,
    trace_end_detected,
    print_saved_results,
    SessionStatus
)
standard_library.install_aliases()


def pytest_addoption(parser):
    print("Adding options")
    for name, val in CONFIG.items():
        parser.addoption("--{}".format(name),
                         # type=val.value_type,
                         action="store",
                         help=val.help)


@pytest.hookimpl(trylast=True)  # TODO is this still required?
def pytest_configure(config):
    print("phases configuration (loglevels, outputredirect, verify)")
    # Load user defined configuration from file (config.cfg)
    config_path = pkg_resources.resource_filename('pytest_phases', '')
    parser = ConfigParser()
    parser.read(os.path.join(config_path, "config.cfg"))

    for func in list(DEBUG.keys()):
        try:
            DEBUG[func].enabled = parser.getboolean("debug", func)
        except Exception as e:
            print(e)

    for option in list(CONFIG.keys()):
        try:
            if CONFIG[option].value_type is int:
                CONFIG[option].value = parser.getint("general", option)
            elif CONFIG[option].value_type is bool:
                CONFIG[option].value = parser.getboolean("general", option)
            else:
                CONFIG[option].value = parser.get("general", option)
        except Exception as e:
            print(e)

    for name, val in CONFIG.items():
        cmd_line_val = config.getoption("--{}".format(name))
        if cmd_line_val:
            if CONFIG[name].value_type is bool:
                if cmd_line_val.lower() in ("1", "yes", "true", "on"):
                    CONFIG[name].value = True
                elif cmd_line_val.lower() in ("0", "no", "false", "off"):
                    CONFIG[name].value = False
            else:
                CONFIG[name].value = CONFIG[name].value_type(cmd_line_val)

    print("pytest-phases configuration:")
    for option in list(CONFIG.keys()):
        print("{0}: type={1.value_type}, val={1.value}".format(option, CONFIG[
            option]))

    # User defined mongo DB configuration (mongo.cfg)
    parser.read(os.path.join(config_path, "mongo.cfg"))
    mongo_hosts = parser.get("general", "hosts").split(",")
    mongo_enable = parser.getboolean("general", "enable")
    mongo_db = parser.get("general", "db")

    SessionStatus.mongo = MongoConnector(mongo_enable, mongo_hosts, mongo_db)

    if not CONFIG["no-redirect"].value:
        debug_print("Perform output redirection", DEBUG["output-redirect"])
        log_redirect = LogOutputRedirection()
        sys.stderr = log_redirect
        sys.stdout = log_redirect
    if CONFIG["no-json"].value:
        LogOutputRedirection.json_log = False
        debug_print("JSON logging is disabled (command line)",
                    DEBUG["output-redirect"])

    debug_print("Using root directory '{}'".format(CONFIG["root-dir"].value),
                DEBUG["output-redirect"])
    LogOutputRedirection.root_directory = CONFIG["root-dir"].value
    if not os.path.exists(LogOutputRedirection.root_directory):
        debug_print("Creating directories {}"
                    .format(LogOutputRedirection.root_directory),
                    DEBUG["output-redirect"])
        os.makedirs(LogOutputRedirection.root_directory)

    open(os.path.join(LogOutputRedirection.root_directory, "session.json"),
         'w').close()
    LogOutputRedirection.session_file_path = os.path.join(
        LogOutputRedirection.root_directory, "session.json")


def pytest_collection_modifyitems(session, config, items):
    debug_print(session, DEBUG["mongo"])
    debug_print(config, DEBUG["mongo"])
    debug_print(items, DEBUG["mongo"])
    # just the test name - .name
    # Could change this to include class and module - ._nodeid
    # Could add fixtures - .fixturenames (probably overkill)
    test_names = [i.name for i in items]
    SessionStatus.mongo.init_session(test_names)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    debug_print("Creating log file for module {}, test function {}".format(
        item.module.__name__, item.name), DEBUG["output-redirect"])

    if LogOutputRedirection.json_log:
        # Create module dir if required and test function dir within
        # this and then module_function.json file
        path_to_test_dir = os.path.join(LogOutputRedirection.root_directory,
                                        item.module.__name__, item.name)
        debug_print("Path to test directory: {}".format(path_to_test_dir),
                    DEBUG["output-redirect"])
        if not os.path.exists(path_to_test_dir):
            debug_print("Creating directories", DEBUG["output-redirect"])
            os.makedirs(path_to_test_dir)

        open(os.path.join(path_to_test_dir, "log.json"), 'w').close()
        LogOutputRedirection.test_file_path = os.path.join(path_to_test_dir,
                                                           "log.json")
        debug_print("Path to json log file: {}".format(
            LogOutputRedirection.test_file_path), DEBUG["output-redirect"])

    debug_print("Test SETUP for test {0}".format(item.name),
                DEBUG["phases"])
    debug_print("Test {0.name} SETUP has fixtures: {0.fixturenames}".format(
        item), DEBUG["scopes"])

    # SessionStatus.session = None
    # SessionStatus.class_name = None # TODO Not sure why these were here
    # SessionStatus.module = None     # and the effect of removing them?

    def get_module_class(item, new_parents):
        """
        Recurse through the test's (item) parents and set the current
        module and class.
        :param item: The pytest test item.
        :param new_parents: Dictionary of new parents (class and
        module).
        :return: A dictionary containing module and class names if they
        are new.
        """
        if isinstance(item.parent, Class):
            debug_print("Class is {}".format(item.parent.name),
                        DEBUG["phases"])
            if SessionStatus.class_name != item.parent.name:
                new_parents["class"] = item.parent.name
            SessionStatus.class_name = item.parent.name
        if isinstance(item.parent, Module):
            debug_print("Module is {} ({})".format(item.parent.name,
                                                   SessionStatus.module),
                        DEBUG["phases"])
            if SessionStatus.module != item.parent.name:
                new_parents["module"] = item.parent.name
            SessionStatus.module = item.parent.name
        # if isinstance(item.parent, Session):
        #     debug_print("Session is {}".format(item.parent.name),
        #                  DEBUG["scopes"])
        #     SessionStatus.session = item.parent.name
            # Module is highest level parent currently supported
            return new_parents
        next_item = item.parent
        if "parent" in list(next_item.__dict__.keys()):
            if next_item.parent:
                get_module_class(next_item, new_parents)
        return new_parents
    parents = get_module_class(item, {"class": None, "module": None})
    debug_print("Test parents (None if same as previous test):",
                DEBUG["phases"], prettify=parents)

    # Set test session globals
    # Run order - tuples of (parent module, test function name)
    # SessionStatus.run_order.append((item.parent.name, item.name))
    SessionStatus.run_order.append((SessionStatus.module,
                                    SessionStatus.class_name,
                                    item.name))
    # TODO module if initial parent was class, otherwise session
    # item.parent.parent.name

    # Set test fixtures here (for tests without function fixtures or having
    # fixtures that are already setup). Overridden in pytest_fixture_setup
    # if it is executed.
    SessionStatus.test_fixtures[item.name] = list(SessionStatus.active_setups)

    current_log_index = get_current_index()
    # No logs are associated with the test until the testresult and
    # loglink documents are inserted below
    SessionStatus.test_object_id = SessionStatus.mongo.init_test_result(
        item.name, item.fixturenames[:-1], parents["class"], parents["module"]
    )
    pytest.log.high_level_step("STARTING TEST {}".format(item.name))

    outcome = yield
    debug_print("Test SETUP - Complete {}, outcome: {}".format(item, outcome),
                DEBUG["phases"])
    # DEBUG This is only here to double check that the fixture has raised
    # the correct exception
    # TODO check if an assertion could come from anywhere other than a fixture
    raised_exc = outcome.excinfo
    debug_print("Test SETUP - Raised exception: {}".format(raised_exc),
                DEBUG["phases"])

    # TODO could this be done at start of pytest_pyfunc_call?
    SessionStatus.phase = "call"


# Introduced in pytest 3.0.0
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    debug_print("Fixture SETUP for {0.argname} with {0.scope} scope"
                .format(fixturedef), DEBUG["scopes"])

    # Setting the phase, test_function, active_setups and test_fixtures is
    # done here (rather than in pytest_runtest_setup) as a workaround for
    # pytest bug https://github.com/pytest-dev/pytest/issues/3032
    SessionStatus.phase = "setup"
    test_name = request._pyfuncitem.name
    SessionStatus.test_function = test_name
    fixture_name = fixturedef.argname

    for test_func in SessionStatus.active_setups:
        # Remove any fixtures not already removed (in
        # pytest_fixture_post_finalizer) - parameterized module scoped
        # fixtures. Search for "[" to ensure fixture is parameterized.
        if test_func.startswith("{}[".format(fixture_name)):
            SessionStatus.active_setups.remove(test_func)
            # TODO raise a (pytest-)warning

    if hasattr(request, "param"):
        setup_params = "[{}]".format(request.param)
    else:
        setup_params = ""
    setup_args = "{}{}".format(fixture_name, setup_params)
    SessionStatus.active_setups.append(setup_args)
    SessionStatus.test_fixtures[SessionStatus.test_function] = \
        list(SessionStatus.active_setups)
    SessionStatus.exec_func_fix = setup_args
    # SessionStatus.mongo.update_test_result(
    #     {"_id": SessionStatus.test_object_id},
    #     {"$set": {"fixtures": SessionStatus.test_fixtures[SessionStatus.test_function]}})

    res = yield
    debug_print("Fixture setup (after yield): {}".format(res),
                DEBUG["scopes"], prettify=res.__dict__)
    if res._excinfo:
        # An exception was raised by the fixture setup
        debug_print("{}".format(res._excinfo[0].__dict__),
                    DEBUG["scopes"])
        if res._excinfo[0] not in (WarningException, VerificationException):
            # Detect a regular assertion (assert) raised by the setup phase.
            # Save it so it is printed in the results table.
            _save_non_verify_exc(res._excinfo)
            set_saved_raised()  # FIXME is this required?
            # TODO in future we'd like to be able to specify the Exception
            # type from the verify function so this would have to change. We
            # could check if the traceback object address is already saved
    # TODO unsure how to detect skip etc. here

    debug_print("Fixture SETUP for {0.argname} with {0.scope} scope COMPLETE"
                .format(fixturedef), DEBUG["scopes"])
    SessionStatus.verifications.fixture_setup_raise_saved(fixture_name,
                                                          test_name)


# Introduced in pytest 3.0.0
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_post_finalizer(fixturedef, request):
    # FIXME check that the phase is teardown
    debug_print("Fixture TEARDOWN for {0.argname} with {0.scope} scope"
                .format(fixturedef), DEBUG["scopes"])

    # fixturedef.cached_result is always (None, 0, none) so use
    # sys.exc_info instead
    exc_info = sys.exc_info()
    debug_print("Fixture teardown exc_info: {}".format(exc_info),
                DEBUG["scopes"])
    if exc_info:
        # An exception was raised by the fixture setup
        # debug_print("{}".format(exc_info[0].__dict__), DEBUG["scopes"])
        if exc_info[0] not in (WarningException, VerificationException, None):
            # Cover case of exc_info being (None, None, None)
            # Detect a regular assertion (assert) raised by the teardown phase.
            # Save it so it is printed in the results table.
            _save_non_verify_exc(exc_info)
            set_saved_raised()  # FIXME is this required?
            # TODO in future we'd like to be able to specify the Exception
            # type from the verify function so this would have to change. We
            # could check if the traceback object address is already saved
    # TODO unsure how to detect skip etc. here

    debug_print("Fixture TEARDOWN for {0.argname} with {0.scope} scope "
                "COMPLETE".format(fixturedef), DEBUG["scopes"])
    fixture_name = fixturedef.argname
    test_name = request._pyfuncitem.name
    SessionStatus.verifications.fixture_teardown_raise_saved(fixture_name,
                                                             test_name)

    res = yield
    # DEBUG seem to get multiple module based executions of this code ???
    debug_print("Fixture post finalizer (after yield): {}".format(res),
                DEBUG["scopes"], prettify=res.__dict__)

    if hasattr(request, "param"):
        setup_params = "[{}]".format(request.param)
    else:
        setup_params = ""
    setup_args = "{}{}".format(fixturedef.argname, setup_params)
    # keep track of previous (this) teardown fixture
    SessionStatus.prev_teardown = setup_args
    try:
        SessionStatus.active_setups.remove(setup_args)
    except ValueError as e:
        print(e)


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    debug_print("CALL - Starting {}".format(pyfuncitem.name), DEBUG["phases"])
    SessionStatus.exec_func_fix = pyfuncitem.name
    SessionStatus.test_function = pyfuncitem.name
    # Update mongo test result
    # SessionStatus.mongo.update_test_result(
    #     {"_id": SessionStatus.test_object_id},
    #     {"$set": {"testFunction": SessionStatus.test_function}})

    i = get_current_index()
    # FIXME keep track of current test ObjectId or find it every time?
    query = {"_id": SessionStatus.test_object_id}
    update = {"$set": {"call": {"logStart": i}}}
    debug_print("Updating oid {}".format(query), DEBUG["mongo"])
    # SessionStatus.mongo.update_test_result(query, update)

    outcome = yield
    debug_print("CALL - Completed {}, outcome {}".format(pyfuncitem, outcome),
                DEBUG["phases"])
    # outcome.excinfo may be None or a (cls, val, tb) tuple
    raised_exc = outcome.excinfo
    debug_print("CALL - Caught exception: {}".format(raised_exc),
                DEBUG["phases"])
    if raised_exc:
        if raised_exc[0] not in (WarningException, VerificationException):
            # For exceptions other than Warning and Verifications:
            # * save the exceptions details and traceback so they are
            # printed in the final test summary,
            # * re-raise the exception
            _save_non_verify_exc(raised_exc)
            set_saved_raised()
            raise_(*raised_exc)

    # Re-raise first VerificationException not yet raised
    # Saved and immediately raised VerificationExceptions are raised here.
    _raise_first_saved_exc_type(VerificationException)
    # Else re-raise first WarningException not yet raised
    if CONFIG["raise-warnings"].value:
        _raise_first_saved_exc_type(WarningException)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    debug_print("Test TEARDOWN - Starting {}".format(item), DEBUG["phases"])
    SessionStatus.phase = "teardown"

    i = get_current_index()
    # FIXME keep track of current test ObjectId or find it every time?
    query = {"_id": SessionStatus.test_object_id}
    update = {"$set": {"teardown": {"logStart": i}}}
    debug_print("Updating oid {}".format(query), DEBUG["mongo"])
    # SessionStatus.mongo.update_test_result(query, update)

    outcome = yield
    debug_print("Test TEARDOWN - completed {}, outcome: {}".format(item,
                outcome), DEBUG["phases"])

    raised_exc = outcome.excinfo
    debug_print("Test TEARDOWN - Raised exception: {}".format(raised_exc),
                DEBUG["phases"])


def _raise_existing_setup_error():
    module_name, class_name, test_func = SessionStatus.run_order[-1]
    fixture_results = {"setup": {"overall": {}}}
    # Module scoped fixtures
    m_res = _filter_scope_phase("module", "module", module_name, "setup")
    debug_print("Test fixtures for test {}: {}".format(test_func,
                SessionStatus.test_fixtures[test_func]), DEBUG["scopes"])

    # Remove module results for fixtures not listed in
    # SessionStatus.test_fixtures[test_function]
    m_res_cut = []
    for res in m_res:
        if res.fixture_name in SessionStatus.test_fixtures[test_func]:
            m_res_cut.append(res)
    fixture_results["setup"]["module"] = _filter_fixture(m_res_cut)
    # Class scoped fixtures
    c_res = _filter_scope_phase("class_name", "class", class_name,
                                "setup")
    c_res_cut = []
    for res in c_res:
        if res.fixture_name in SessionStatus.test_fixtures[test_func]:
            c_res_cut.append(res)
    fixture_results["setup"]["class"] = _filter_fixture(c_res_cut)
    debug_print("Module and class scoped setup results and summary (current "
                "test only): {}".format(fixture_results), DEBUG["scopes"])

    # Results for setup fixtures applied to this test associated with earlier
    # test functions
    existing_setup_results = []
    for scope in ("module", "class"):
        if fixture_results["setup"][scope]:
            for res in list(fixture_results["setup"][scope].values())[0][:-1]:
                existing_setup_results.append(res)
    debug_print("Module and class scoped setup results (current test only): "
                "{}".format(existing_setup_results), DEBUG["scopes"])
    for res in existing_setup_results:
        if res.traceback_link:
            # FIXME raise failed verification over warnings
            exc_type = res.traceback_link.exc_type
            msg = "{0.msg} - {0.status}".format(res)
            tb = res.traceback_link.exc_traceback
            debug_print("Raising a setup error (inc errors pytest has already "
                        "associated with a previous test)", DEBUG["scopes"])
            debug_print("Raising: {} {} {}".format(exc_type, msg, tb),
                        DEBUG["scopes"])
            set_saved_raised()
            raise_(exc_type, msg, tb)


def _save_non_verify_exc(raised_exc, use_prev_teardown=False):
    exc_msg = str(raised_exc[1]).strip().replace("\n", " ")
    stack_trace = traceback.extract_tb(raised_exc[2])

    # DO NOT RELY ON THIS METHOD BEING CONSISTENT BETWEEN PYTEST VERSIONS
    # Try to extract a pytest failure method from the traceback type name
    try:
        trace_name = raised_exc[0].__name__.lower()
    except AttributeError:
        trace_name = None

    if trace_name == "skipped":
        # Pytest special case - skip
        # Note that this also covers pytest.importorskip
        debug_print("Pytest Skip detected in traceback", DEBUG["verify"])
        failure_type = "SKIP"
        exc_type = "S"
    elif trace_name == "xfailed":
        debug_print("Pytest XFail detected in traceback", DEBUG["verify"])
        failure_type = "XFAIL"
        exc_type = "X"
    else:
        # General failure for AssertionError, TypeError etc. The traceback
        # provides the greater exception detail
        # Note that this also covers pytest.fail
        failure_type = "FAIL"
        exc_type = "O"

    debug_print("Saving caught exception (non-plugin): {}, {}".format(
        exc_type, exc_msg), DEBUG["verify"])

    frame = raised_exc[2]
    # stack_trace is a list of stack trace tuples for each
    # stack depth (filename, line number, function name*, text)
    # "text" only gets the first line of a call multi-line call
    # stack trace is None if source not available.

    # Get the locals for each traceback entry - required to identify the
    # fixture scope
    # FIXME is there a better way to do this - have to cycle through all
    # frames to get to the most recent
    locals_all_frames = []
    while frame:
        # TODO enhancement: remove keys starting with "@py_"
        locals_all_frames.append(frame.tb_frame.f_locals)
        frame = frame.tb_next
    debug_print("all frames locals: {}".format(locals_all_frames),
                 DEBUG["verify"])

    trace_complete = []
    for i, tb_level in enumerate(reversed(stack_trace)):
        level_detail = dict(
            location="",  # module::line#::function
            # TODO is a dict required here or is it always converted to str?
            locals=dict(),  # dictionary of locals
            code=[]  # source code (multiple lines possible in future
            # enhancement - for saved verifications ONLY)
        )
        if (CONFIG["traceback-stops-at-test-functions"].value and
                trace_end_detected(tb_level[3])):
            break
        level_detail['code'].append(">   {0[3]}".format(tb_level))
        if CONFIG["include-all-local-vars"].value:
            level_detail['locals'] = locals_all_frames[-(i+1)]
        level_detail['location'] = "{0[0]}:{0[1]}:{0[2]}".format(tb_level)
        trace_complete.insert(0, level_detail)

    # Divide by 3 as each failure has 3 lines (list entries)
    debug_print("# of tracebacks: {}".format(old_div(len(trace_complete), 3)),
                DEBUG["verify"])
    debug_print("length of locals: {}".format(len(locals_all_frames)),
                DEBUG["verify"])
    if DEBUG["verify"]:
        for line in trace_complete:
            debug_print(line, DEBUG["verify"])

    fixture_name = None
    fixture_scope = None
    for i, stack_locals in enumerate(reversed(locals_all_frames)):
        # Most recent stack entry first
        # Extract the setup/teardown fixture information if possible
        # keep track of the fixture name and scope
        for item in list(stack_locals.values()):
            if isinstance(item, FixtureDef):
                fixture_name = item.argname
                fixture_scope = item.scope
                debug_print("scope for {} is {} [{}]".format(fixture_name,
                            fixture_scope, i), DEBUG["verify"])
        if fixture_scope:
            break

    debug_print("saving: {}, {}".format(fixture_name, fixture_scope),
                DEBUG["verify"])

    # TODO refactor the saved_results format- make it an object
    s_res = SessionStatus.verifications.saved_results
    s_tb = SessionStatus.verifications.saved_tracebacks
    s_tb.append(FailureTraceback(raised_exc[0], raised_exc[2], trace_complete,
                                 raised=True))
    if CONFIG["include-all-local-vars"].value:
        module_function_line = trace_complete[-3]
    else:
        module_function_line = trace_complete[-2]
    result = Result(exc_msg, failure_type, exc_type, fixture_scope,
                    module_function_line, [trace_complete[-1]],
                    True, source_locals=locals_all_frames[-1],
                    fail_traceback_link=s_tb[-1],
                    use_prev_teardown=use_prev_teardown)
    s_res.append(result)
    s_tb[-1].result_link = s_res[-1]
    SessionStatus.mongo.insert_verification(result)


def _raise_first_saved_exc_type(type_to_raise):
    for i, saved_traceback in enumerate(SessionStatus.verifications.saved_tracebacks):
        exc_type = saved_traceback.exc_type
        debug_print("saved traceback index: {}, type: {}, searching for: {}"
                    .format(i, exc_type, type_to_raise), DEBUG["verify"])
        if exc_type == type_to_raise and not saved_traceback.raised:
            msg = "{0.msg} - {0.status}".format(saved_traceback.result_link)
            tb = saved_traceback.exc_traceback
            print("Re-raising first saved {}: {} {} {}"
                  .format(type_to_raise, exc_type, msg, tb))
            set_saved_raised()
            raise_(exc_type, msg, tb)  # for python 2 and 3 compatibility


@pytest.hookimpl(hookwrapper=True)
def pytest_report_teststatus(report):
    debug_print("TEST REPORT FOR {} PHASE: {}".format(report.when,
                report.outcome), DEBUG["phases"])
    result = yield
    # result-category, shortletter and verbose word for reporting
    # use result-category to detect xfail etc.
    result_category = result._result[0]
    # TODO Check that empty '' result_category refers to undefined test
    # reports - passed setup or teardown only
    debug_print("result category: {}".format(result_category),
                DEBUG["phases"])
    # Get the saved results, saved result summary and the phase outcome
    SessionStatus.verifications.phase_summary_and_outcome(report.when,
                                                          result_category)

    if report.when == "teardown":
        # FIXME this is just for a single test
        debug_print("OUTPUTREDIRECT LAST TEARDOWN MESSAGE",
                    DEBUG["output-redirect"])
        LogOutputRedirection.test_file_path = None


def print_new_results(phase):
    for i, s_res in enumerate(SessionStatus.verifications.saved_results):
        res_info = s_res["Extra Info"]
        if res_info.phase == phase and not res_info.printed:
            debug_print("Valid result ({}) found with info: {}"
                        .format(i, res_info.format_result_info()),
                        DEBUG["scopes"])
            res_info.printed = True


@pytest.hookimpl(hookwrapper=True)
def pytest_terminal_summary(terminalreporter):
    """ override the terminal summary reporting. """
    debug_print("In pytest_terminal_summary", DEBUG["summary"])
    if DEBUG["summary"]:
        debug_print("Run order:", DEBUG["summary"])
        for module_class_function in SessionStatus.run_order:
            debug_print("{0[0]}::{0[1]}::{0[2]}".format(module_class_function),
                        DEBUG["summary"])

    # if DEBUG["verify"]:
    #     print "Saved Results (dictionaries)"
    #     for i, res in enumerate(Verifications.saved_results):
    #         print "{} - {}".format(i, res.__dict__)
    #     print "Saved Tracebacks (dictionaries)"
    #     for i, tb in enumerate(Verifications.saved_tracebacks):
    #         print "{} - {}".format(i, tb.__dict__)

    if DEBUG["verify"]:
        for saved_tb in SessionStatus.verifications.saved_tracebacks:
            debug_print("Result {0.result_link} linked to traceback {0}"
                        .format(saved_tb), DEBUG["verify"])

    # Retrieve the saved results and traceback info for any failed
    # verifications.
    # Results table
    print_saved_results()

    debug_print("Test function fixture dependencies:", DEBUG["summary"])
    for test_name, setup_fixtures in SessionStatus.test_fixtures.items():
        debug_print("{} depends on setup fixtures: {}"
                    .format(test_name, ", ".join(setup_fixtures)),
                    DEBUG["summary"])

    # DEBUG ONLY
    # Collect all the results for each reported phase/scope(/fixture)
    result_by_fixture = OrderedDict()
    debug_print("Scope/phase saved results summary in executions order:",
                DEBUG["summary"])
    for saved_result in SessionStatus.verifications.saved_results:
        key = "{0.fixture_name}:{0.test_function}:{0.phase}:{0.scope}"\
            .format(saved_result)
        if key not in result_by_fixture:
            result_by_fixture[key] = {}
            result_by_fixture[key][saved_result.type_code] = 1
        elif saved_result.type_code not in result_by_fixture[key]:
            result_by_fixture[key][saved_result.type_code] = 1
        else:
            result_by_fixture[key][saved_result.type_code] += 1
    for key, val in result_by_fixture.items():
        debug_print("{}: {}".format(key, val), DEBUG["summary"])
    # DEBUG END

    # Consolidated test results - plugin saved results and parsed pytest
    # reports
    test_results = OrderedDict()
    # Search backwards through the fixture results to find setup results
    for module_class_function in SessionStatus.run_order:
        module_name, class_name, test_func = module_class_function
        debug_print("Setup teardown fixture results to collate: {}".format(
            SessionStatus.test_fixtures[test_func]), DEBUG["summary"])

        # TODO if no fixtures in fixture_results the phase must be passed
        # fixtures = SessionStatus.test_fixtures[test_function]

        fixture_results = {}
        for phase in ("setup", "teardown"):
            fixture_results[phase] = {"overall": {}}
            # Module scoped fixtures
            m_res = _filter_scope_phase("module", "module", module_name, phase)
            # remove module results for fixtures not listed in
            # SessionStatus.test_fixtures[test_function]
            m_res_cut = []
            for res in m_res:
                if res.fixture_name in SessionStatus.test_fixtures[test_func]:
                    m_res_cut.append(res)
            fixture_results[phase]["module"] = _filter_fixture(m_res_cut)
            # Class scoped fixtures
            c_res = _filter_scope_phase("class_name", "class", class_name,
                                        phase)
            fixture_results[phase]["class"] = _filter_fixture(c_res)
            # Function scoped fixtures
            f_res = _filter_scope_phase("test_function", "function",
                                        test_func, phase)
            fixture_results[phase]["function"] = _filter_fixture(f_res)
        # Call (test function) results
        call = [x for x in SessionStatus.verifications.saved_results
                if x.test_function == test_func and x.phase == "call"]
        call_res_summary = _results_summary(call)
        fixture_results["call"] = {"results": call,
                                   "overall": {"saved": call_res_summary}}
        test_results[test_func] = fixture_results

    # Parse the pytest reports
    # Extract report type, outcome, duration, when (phase), location (test
    # function).
    # Session based reports (CollectReport, (pytest-)WarningReport) are
    # collated for printing later.
    pytest_reports = terminalreporter.stats
    reports_total = sum(len(v) for k, v in list(pytest_reports.items()))
    debug_print("{} pytest reports".format(reports_total), DEBUG["summary"])
    total_session_duration = 0
    collect_error_reports = []
    pytest_warning_reports = []
    summary_results = {}
    for report_type, reports in pytest_reports.items():
        for report in reports:
            debug_print("Report type: {}, report: {}".format(
                report_type, report), DEBUG["summary"])
            if isinstance(report, CollectReport):
                # Don't add to test_results dictionary
                debug_print("Found CollectReport", DEBUG["summary"])
                collect_error_reports.append(report)
                if "collection error" not in summary_results:
                    summary_results["collection error"] = 1
                else:
                    summary_results["collection error"] += 1
            elif isinstance(report, WarningReport):
                debug_print("Found WarningReport", DEBUG["summary"])
                pytest_warning_reports.append(report)
                if "pytest-warning" not in summary_results:
                    summary_results["pytest-warning"] = 1
                else:
                    summary_results["pytest-warning"] += 1
            else:
                parsed_report = {
                    "type": report_type,
                    "pytest-outcome": report.outcome,
                    "duration": report.duration
                }
                total_session_duration += report.duration
                # test report location[2] for a standalone test function
                # within a module is just the function name, for class
                # based tests it is in the format:
                # class_name.test_function_name
                # DEBUG could be retrieved from nodeid .split(":")[-1]
                test_results[report.location[2].split(".")[-1]][report.when][
                    "overall"]["pytest"] = parsed_report

    # For each test: determine the result for each phase and the overall test
    # result.
    for test_function, test_result in test_results.items():
        for phase in ("setup", "teardown"):
            test_result[phase]["overall"]["saved"] = {}
            for scope in ("module", "class", "function"):
                for fixture_name, fixture_result in test_result[phase][scope].items():
                    for k, v in fixture_result[-1].items():
                        if k in test_result[phase]["overall"]["saved"]:
                            test_result[phase]["overall"]["saved"][k] += v
                        else:
                            test_result[phase]["overall"]["saved"][k] = v
            # Overall phase result (use the plugins saved results and the
            # pytest report outcome
            test_result[phase]["overall"]["result"] = phase_specific_result(
                phase,
                _get_phase_summary_result(test_result[phase]["overall"]))
        test_result["call"]["overall"]["result"] = \
            _get_phase_summary_result(test_result["call"]["overall"])

        test_result["overall"] = _get_test_summary_result(
            test_result["setup"]["overall"]["result"],
            test_result["call"]["overall"]["result"],
            test_result["teardown"]["overall"]["result"])
        # Increment the test result outcome counter
        if test_result["overall"] not in summary_results:
            summary_results[test_result["overall"]] = 1
        else:
            summary_results[test_result["overall"]] += 1

    for test_function, fixture_results in test_results.items():
        pytest.log.high_level_step("Summary of results for test {}, overall: "
                                   "{}".format(test_function,
                                               fixture_results["overall"]))
        for phase in ("setup", "call", "teardown"):
            if phase == "setup":
                pytest.log.detail_step(
                    "Setup ({0}), overall: {1[result]}, saved results: "
                    "{1[saved]}".format(test_function,
                                        fixture_results[phase]["overall"]))
                for scope in ("module", "class", "function"):
                    for fixture_name, results in fixture_results[phase][scope]\
                            .items():
                        results_id = [hex(id(x))[-4:] for x in results[0:-1]]
                        pytest.log.step("Fixture {} (scope: {}) saved results:"
                                        " {}".format(fixture_name, scope,
                                                    results[-1]),
                                        log_level=3)
                        debug_print(results_id, DEBUG["summary"])
            elif phase == "teardown":
                pytest.log.detail_step(
                    "Teardown ({0}), overall: {1[result]}, saved results: "
                    "{1[saved]}".format(test_function,
                                        fixture_results[phase]["overall"]))
                for scope in ("function", "class", "module"):
                    for fixture_name, results in fixture_results[phase][scope]\
                            .items():
                        results_id = [hex(id(x))[-4:] for x in results[0:-1]]
                        pytest.log.step("Fixture {} (scope: {}) saved results:"
                                        " {}".format(fixture_name, scope,
                                                    results[-1]),
                                        log_level=3)
                        debug_print(results_id, DEBUG["summary"])
            elif phase == "call":
                pytest.log.detail_step(
                    "Call (test function {0}), overall: {1[result]}, saved "
                    "results: {1[saved]}".format(test_function,
                                                 fixture_results[phase][
                                                   "overall"]))
                results_id = [hex(id(x))[-4:] for x in fixture_results[phase][
                    "results"]]
                debug_print(results_id, DEBUG["summary"])
            if "overall" in fixture_results[phase]:
                debug_print("Phase overall: {}".format(
                    fixture_results[phase]["overall"]), DEBUG["summary"])

    # Print the expected fail, unexpected pass and skip reports exactly as
    # pytest does.
    lines = []
    show_xfailed(terminalreporter, lines)
    show_xpassed(terminalreporter, lines)
    show_skipped(terminalreporter, lines)
    # Print the reports of the collected
    for report in collect_error_reports:
        lines.append("COLLECTION ERROR {}".format(report.longrepr))
    for report in pytest_warning_reports:
        lines.append("PYTEST-WARNING {} {}".format(report.nodeid,
                                                   report.message))
    if lines:
        pytest.log.high_level_step("collection error, skip, xFail/xPass and "
                                   "pytest-warning reasons (short test summary "
                                   "info)")
        for line in lines:
            pytest.log.detail_step(line)
    else:
        pytest.log.high_level_step("No collection errors, skips, xFail/xPass or "
                                   "pytest-warnings")

    session_duration = time.time() - terminalreporter._sessionstarttime
    debug_print("All tests result summary: {}. Session duration: {}s (sum of "
                "phases: {}s)".format(summary_results, session_duration,
                                      total_session_duration),
                DEBUG["summary"])

    outcomes = []
    for outcome in hierarchy:
        if outcome in summary_results:
            if summary_results[outcome] > 1:
                outcome_message = plural(outcome)
            else:
                outcome_message = outcome
            outcomes.append("{} {}".format(summary_results[outcome],
                                           outcome_message))
    summary_line = "{0} in {1:.2f}s".format(", ".join(outcomes),
                                            session_duration)
    pytest.log.high_level_step(summary_line)

    # # DEBUG ONLY
    # # Passes never seems to print anything - no summary?
    # _print_summary(terminalreporter, "passes")
    # _print_summary(terminalreporter, "warnings")  # pytest-warnings
    # # TODO split failures into failures and warnings - the traceback already
    # # printed in the results table is all that is required
    # _print_summary(terminalreporter, "failures")
    # _print_summary(terminalreporter, "errors")
    # _print_summary(terminalreporter, "deselected")
    _print_summary(terminalreporter, "stats")  # same as terminalreporter.
    # summary_stats()
    # # END OF DEBUG

    # Exit now and don't print the original pytest summary
    exit()  # FIXME use correct exit code - how does pytest decide this?
    # print("Anything following this message is the original pytest code")


def _print_summary(terminalreporter, report):
    # print "********** {} **********".format(report)
    # writes directly - does not return anything
    getattr(terminalreporter, "summary_{}".format(report))()


def _get_phase_summary_result(overall):
    # overall dict example contents
    # {'pytest': {'pytest-outcome': 'failed',
    #             'duration': 0.02312016487121582,
    #             'type': 'error'},
    # 'saved': {'P': 1, 'W': 1}}
    if "pytest" not in overall:
        # TODO check this is the call phase
        return "not run (no report)"
    for result_condition, result_text in outcome_conditions:
        # debug_print("Checking saved results: {}, condition result = {}"
        #             .format(overall, result_condition(overall)),
        #             DEBUG["summary"])
        if result_condition(overall):
            return result_text  # falls out to "passed" if no other


def _get_test_summary_result(setup_result, call_result, teardown_result):
    for outcome in hierarchy[:11]:
        if outcome in (setup_result, call_result, teardown_result):
            return outcome
    if setup_result == Outcomes.passed and call_result == Outcomes.passed and \
            teardown_result == Outcomes.passed:
        return Outcomes.passed


def _filter_scope_phase(result_att, scope, scope_name, phase):
    s_r = SessionStatus.verifications.saved_results
    scope_results = [x for x in s_r if getattr(x, result_att) == scope_name
                           and x.scope == scope]
    return [y for y in scope_results if y.phase == phase]


# TODO refactor usages and remove
def _results_summary(results):
    summary = {}
    for result in results:
        if result.type_code not in summary:
            summary[result.type_code] = 1
        else:
            summary[result.type_code] += 1
    return summary


def _filter_fixture(results):
    results_by_fixture = OrderedDict()
    for res in results:
        if res.fixture_name not in results_by_fixture:
            results_by_fixture[res.fixture_name] = [res]
        else:
            results_by_fixture[res.fixture_name].append(res)
    for fix_name, fix_results in results_by_fixture.items():
        f_res_summary = _results_summary(fix_results)
        results_by_fixture[fix_name].append(f_res_summary)
    return results_by_fixture


# TODO check if all these are required in the namespace
def pytest_namespace():
    # Add verify functions to the pytest namespace
    def verify(fail_condition, fail_message, raise_immediately=True,
               warning=False, warn_condition=None, warn_message=None,
               full_method_trace=False, stop_at_test=True, log_level=None):
        """Print a message at the highest log level."""
        perform_verification(fail_condition, fail_message, raise_immediately,
                             warning, warn_condition, warn_message,
                             full_method_trace, stop_at_test, log_level)

    name = {"log": LogLevel,
            "verify": verify}
    return name
