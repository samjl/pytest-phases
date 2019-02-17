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
import traceback
from builtins import str
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
    MONGO_CONFIG,
    WEB_SERVER_CONFIG,
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
    outcome_conditionals,
    phase_specific_result,
    hierarchy
)
from .outputredirect import LogOutputRedirection  # FIXME replace with get
from .verify import (
    VerificationException,
    WarningException,
    FailureTraceback,
    Result,
    set_saved_raised,
    trace_end_detected,
    print_results,
    SessionStatus
)
standard_library.install_aliases()


def pytest_addoption(parser):
    for name, val in dict(CONFIG, **MONGO_CONFIG, **WEB_SERVER_CONFIG).items():
        parser.addoption("--{}".format(name), action="store",
                         help=val.help)


def parse_config_file_options(lookup, section, parser):
    for option in list(lookup.keys()):
        try:
            if lookup[option].value_type is int:
                lookup[option].value = parser.getint(section, option)
            elif lookup[option].value_type is bool:
                lookup[option].value = parser.getboolean(section, option)
            else:
                lookup[option].value = parser.get(section, option)
        except Exception as e:
            print(e)


def parse_cmd_line_options(lookup, pytest_config):
    for name, val in lookup.items():
        cmd_line_val = pytest_config.getoption("--{}".format(name))
        if cmd_line_val:
            if lookup[name].value_type is bool:
                if cmd_line_val.lower() in ("1", "yes", "true", "on"):
                    lookup[name].value = True
                elif cmd_line_val.lower() in ("0", "no", "false", "off"):
                    lookup[name].value = False
            else:
                lookup[name].value = lookup[name].value_type(cmd_line_val)


@pytest.hookimpl(trylast=True)  # TODO is this still required?
def pytest_configure(config):
    print("Performing pytest-phases configuration")
    # Load user defined configuration from file (config.cfg)
    config_path = pkg_resources.resource_filename('pytest_phases', '')
    parser = ConfigParser()

    # Parse config.cfg
    parser.read(os.path.join(config_path, "config.cfg"))
    parse_config_file_options(DEBUG, "debug", parser)
    parse_config_file_options(CONFIG, "general", parser)
    # Parse mongo.cfg
    parser.read(os.path.join(config_path, "mongo.cfg"))
    parse_config_file_options(MONGO_CONFIG, "general", parser)
    parse_config_file_options(WEB_SERVER_CONFIG, "webapp", parser)

    # Command line parameters override values in the .cfg files
    parse_cmd_line_options(CONFIG, config)
    parse_cmd_line_options(MONGO_CONFIG, config)
    parse_cmd_line_options(WEB_SERVER_CONFIG, config)
    print("pytest-phases configuration:")
    # All configuration options (file and command line)
    for option, value in dict(CONFIG, **DEBUG, **MONGO_CONFIG,
                              **WEB_SERVER_CONFIG).items():
        print("{0}:{1.value} (type={1.value_type})".format(option, value))

    SessionStatus.mongo = MongoConnector(
        MONGO_CONFIG["enable"].value,
        MONGO_CONFIG["hosts"].value.split(","),
        MONGO_CONFIG["db"].value
    )

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
    print("http://{}:{}/session?sessionIds={}".format(
        WEB_SERVER_CONFIG["hostname"].value,
        WEB_SERVER_CONFIG["port"].value,
        SessionStatus.mongo.session_id)
    )

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

    # Set the initial test phase outcomes
    SessionStatus.test_outcome[item.name] = {
        "setup": Outcomes.pending,
        "call": Outcomes.pending,
        "teardown": Outcomes.pending
    }

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

    # No logs are associated with the test until the testresult and
    # loglink documents are inserted below
    # current_log_index = get_current_index()  # TODO

    # Get any setup outcomes already completed and valid for this test:  class
    # or module. scope. phase-results: not applicable for "function" scoped
    # fixtures (run after this stage!).
    res, summary, outcome = (SessionStatus.verifications.
                             phase_summary_and_outcome("setup", None,
                                                       function_scope=False))
    # FIXME outcome returns passed if no setups already performed - should
    # be None/in-progress/pending?

    SessionStatus.test_object_id = SessionStatus.mongo.init_test_result(
        item.name, item.fixturenames[:-1], parents["class"], parents["module"],
        outcome
    )

    LogLevel.high_level_step("STARTING TEST {}".format(item.name))

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
    debug_print("Set phase, test, active setups, fixtures (workaround)",
                DEBUG["dev"])
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
    SessionStatus.mongo.init_fixture(fixture_name, fixturedef.scope)

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
    results, summary, outcome = (SessionStatus.verifications.
                                 fixture_setup_results(fixture_name,
                                                       test_name))
    SessionStatus.mongo.update_fixture_setup(fixture_name, outcome, summary)
    # Raise (first) failed verification saved during setup phase or
    SessionStatus.verifications.raise_exc_type(results, VerificationException)
    # else raise (first) warned verification saved during setup phase
    SessionStatus.verifications.raise_exc_type(results, WarningException)


# Introduced in pytest 3.0.0
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_post_finalizer(fixturedef, request):
    # FIXME check that the current set phase is teardown
    debug_print("Fixture TEARDOWN for {0.argname} with {0.scope} scope"
                .format(fixturedef), DEBUG["scopes"])

    # fixturedef.cached_result is always (None, 0, none) so use
    # sys.exc_info instead
    exc_info = sys.exc_info()
    debug_print("Fixture teardown exc_info: {}".format(exc_info),
                DEBUG["scopes"])
    if exc_info:
        # An exception was raised by the fixture teardown
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
    scope = fixturedef.scope
    results, summary, outcome = (SessionStatus.verifications.
                                 fixture_teardown_results(fixture_name,
                                                          test_name))
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
        debug_print("Could not remove fixture from active setups (probably "
                    "removed already) - {}".format(e), DEBUG["scopes"])
    except Exception as e:
        print(str(e))
    else:
        SessionStatus.mongo.update_fixture_teardown(fixturedef.argname,
                                                    outcome, summary, scope)

    res = yield
    # DEBUG seem to get multiple module based executions of this code ???
    debug_print("Fixture post finalizer (after yield): {}".format(res),
                DEBUG["scopes"], prettify=res.__dict__)

    SessionStatus.verifications.raise_exc_type(results, VerificationException)
    SessionStatus.verifications.raise_exc_type(results, WarningException)


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    debug_print("CALL - Starting {}".format(pyfuncitem.name), DEBUG["phases"])
    SessionStatus.exec_func_fix = pyfuncitem.name
    SessionStatus.test_function = pyfuncitem.name
    # Update mongo test result
    # SessionStatus.mongo.update_test_result(
    #     {"_id": SessionStatus.test_object_id},
    #     {"$set": {"testFunction": SessionStatus.test_function}})

    # i = get_current_index()
    # FIXME keep track of current test ObjectId or find it every time?
    # query = {"_id": SessionStatus.test_object_id}
    # update = {"$set": {"call": {"logStart": i}}}
    # debug_print("Updating oid {}".format(query), DEBUG["mongo"])
    # SessionStatus.mongo.update_test_result(query, update)
    SessionStatus.mongo.update_pre_call_phase()

    outcome = yield
    debug_print("CALL - Completed {}, outcome {}".format(pyfuncitem, outcome),
                DEBUG["phases"])
    # outcome.excinfo may be None or a (cls, val, tb) tuple
    raised_exc = outcome.excinfo
    debug_print("CALL - Caught exception: {}".format(raised_exc),
                DEBUG["phases"])
    if raised_exc:
        if raised_exc[0] not in (WarningException, VerificationException):
            # # DEBUG experimental code to retrieve the source code of the
            # # function that rasied an assertion
            # import inspect
            # from _pytest._code.code import ExceptionInfo
            # exc_info_py = ExceptionInfo(tup=raised_exc)
            # calling_func = inspect.getsourcelines(
            #     exc_info_py.traceback[-1]._rawentry
            # )
            # for line in calling_func[0]:
            #     print(line)
            # # tb_report = exc_info_py.getrepr()
            # # print(tb_report)
            # # END OF DEBUG

            # For exceptions other than Warning and Verifications:
            # * save the exceptions details and traceback so they are
            # printed in the final test summary,
            _save_non_verify_exc(raised_exc)
            set_saved_raised()

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

    # i = get_current_index()

    SessionStatus.mongo.update_teardown_phase()

    outcome = yield
    debug_print("Test TEARDOWN - completed {}, outcome: {}".format(item,
                outcome), DEBUG["phases"])
    debug_print("Test TEARDOWN - Raised exception: {}".format(outcome.excinfo),
                DEBUG["phases"])


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

    # Log failed and caught assertion (saved separately to db as
    # verification below)
    LogLevel.verification("{} - FAIL".format(exc_msg), exc_type)
    index = get_current_index()
    # Save the result and traceback
    s_res = SessionStatus.verifications.saved_results
    s_tb = SessionStatus.verifications.saved_tracebacks
    s_tb.append(FailureTraceback(raised_exc[0], raised_exc[2], trace_complete,
                                 raised=True))
    module_function_line = trace_complete[-1]["location"]
    result = Result(exc_msg, failure_type, exc_type, fixture_scope,
                    module_function_line, trace_complete[-1]["code"],
                    True, message_index=index,
                    source_locals=trace_complete[-1]["locals"],
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
    # Update the test name for tests that don't have fixtures associated
    # with them (no function scoped fixtures and no higher scoped fixtures
    # associated with it by pytest (e.g. not first test in module or class).
    test_name = report.location[-1].split('.')[-1]
    SessionStatus.test_function = test_name
    result = yield
    # result-category, shortletter and verbose word for reporting
    # use result-category to detect xfail etc.
    result_category = result._result[0]
    # TODO Check that empty '' result_category refers to undefined test
    # reports - passed setup or teardown only
    debug_print("result category: {}".format(result_category),
                DEBUG["phases"])
    # Get the saved results, saved result summary and the phase outcome
    teardown_results, summary, outcome = (
        SessionStatus.verifications.phase_summary_and_outcome(report.when,
                                                              result_category,
                                                              True)
    )
    SessionStatus.test_outcome[test_name][report.when] = outcome
    SessionStatus.mongo.update_test_phase_complete(report.when, outcome,
                                                   summary)
    # TODO process the duration per phase - report.duration
    # Possible TODO print saved results for each phase - limited use because
    # teardown results cannot be complete for all tests

    if report.when == "teardown":
        # For end of each test
        LogOutputRedirection.test_file_path = None
        # Update the overall test result
        index = len(hierarchy) - 1
        debug_print("Initial outcome is {}".format(hierarchy[index]),
                    DEBUG['phases'])
        for phase_outcome in (SessionStatus.test_outcome[test_name]["setup"],
                              SessionStatus.test_outcome[test_name]["call"],
                              SessionStatus.test_outcome[test_name]["teardown"]):
            phase_outcome_index = hierarchy.index(phase_outcome)
            if phase_outcome_index < index:
                index = phase_outcome_index
        # TODO not preliminary if result is failed
        debug_print("Preliminary test outcome is {}".format(hierarchy[index]),
                    DEBUG['phases'])
        # TODO Print phase results at higher level
        LogLevel.high_level_step("Preliminary test outcome is {}".format(hierarchy[index]))
        LogLevel.detail_step("Note: doesn't include the result of any higher "
                             "scoped teardown functions.")

        # Reset the test name as it is now complete
        SessionStatus.test_function = None

        if not SessionStatus.active_setups:
            # At end of a test module. This assumes that we are not using
            # (or are concerned) about any session scoped fixtures.
            # FIXME or would print for all tests that have no fixtures!
            summary = final_test_outcomes()
            SessionStatus.session_summary.update(summary)
            module_saved_results(SessionStatus.module)
            final_summary(summary)
            # Clear the run order now that the results have been updated
            # and printed
            SessionStatus.run_order = []


def final_test_outcomes():
    summary_results = {}
    for module_class_function in SessionStatus.run_order:
        module_name, class_name, test_func = module_class_function
        results = SessionStatus.verifications.filter_results(
            phase="teardown", scope="class", class_name=class_name)
        results.extend(SessionStatus.verifications.filter_results(
            phase="teardown", scope="module", module_name=module_name))
        results.extend(SessionStatus.verifications.filter_results(
            phase="teardown", scope="function", test_function=test_func))
        # not req to update the outcome
        summary = SessionStatus.verifications._results_summary(results)

        def phase_outcome(saved_summary, pytest_outcome):
            for outcome_condition, outcome in outcome_conditionals:
                if outcome_condition(saved_summary, pytest_outcome):
                    return phase_specific_result("teardown", outcome)

        tear_outcome = phase_outcome(summary, None)
        index = len(hierarchy) - 1
        for phase_outcome in (SessionStatus.test_outcome[test_func]["teardown"],
                              tear_outcome):
            phase_outcome_index = hierarchy.index(phase_outcome)
            if phase_outcome_index < index:
                index = phase_outcome_index
        tear_outcome = hierarchy[index]

        setup_results = SessionStatus.verifications.filter_results(
            phase="setup", scope="class", class_name=class_name)
        setup_results.extend(SessionStatus.verifications.filter_results(
            phase="setup", scope="module", module_name=module_name))
        setup_results.extend(SessionStatus.verifications.filter_results(
            phase="setup", scope="function", test_function=test_func))
        # not req to update the outcome
        setup_summary = SessionStatus.verifications._results_summary(setup_results)

        call_results = (SessionStatus.verifications.filter_results(
            phase="call", test_function=test_func))
        call_summary = SessionStatus.verifications._results_summary(call_results)

        # Get the final test outcome
        index = len(hierarchy) - 1
        for phase_outcome in (SessionStatus.test_outcome[test_func]["setup"],
                              SessionStatus.test_outcome[test_func]["call"],
                              # SessionStatus.test_outcome[test_func]["teardown"],
                              tear_outcome):
            phase_outcome_index = hierarchy.index(phase_outcome)
            if phase_outcome_index < index:
                index = phase_outcome_index
        LogLevel.high_level_step("{} FINAL TEST OUTCOME: {}".format(
            test_func, hierarchy[index]))
        LogLevel.detail_step("Test setup outcome: {}, summary: {}".format(
            SessionStatus.test_outcome[test_func]["setup"], setup_summary))
        LogLevel.detail_step("Test call outcome: {}, summary: {}".format(
            SessionStatus.test_outcome[test_func]["call"], call_summary))
        # This is the final updated test teardown
        LogLevel.detail_step("Test teardown outcome: {}, summary: {}"
                             .format(tear_outcome, summary))

        # Increment the test result outcome counter
        if hierarchy[index] not in summary_results:
            summary_results[hierarchy[index]] = 1
        else:
            summary_results[hierarchy[index]] += 1
    return summary_results


def module_saved_results(module_name):
    print_results(SessionStatus.verifications.filter_results(
        module_name=module_name), alternative_title="MODULE SAVED "
                                                    "VERIFICATIONS")


def final_summary(summary_results):
    outcomes = []
    for outcome in hierarchy:
        if outcome in summary_results:
            if summary_results[outcome] > 1:
                outcome_message = plural(outcome)
            else:
                outcome_message = outcome
            outcomes.append("{} {}".format(summary_results[outcome],
                                           outcome_message))
    LogLevel.high_level_step(", ".join(outcomes))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtestloop(session):
    yield
    SessionStatus.mongo.update_session_complete()


@pytest.hookimpl(hookwrapper=True)
def pytest_terminal_summary(terminalreporter):
    """ override the terminal summary reporting. """
    # DEBUG ONLY
    debug_print("In pytest_terminal_summary", DEBUG["summary"])
    debug_print("Overall session test outcomes (summary) - {}"
                .format(SessionStatus.session_summary), DEBUG["summary"])
    # Check for any outcome other than a passed and
    SessionStatus.session_summary.pop(Outcomes.passed, 0)
    if SessionStatus.session_summary:
        debug_print("Outcomes other than passed exist, exit with error code 1",
                    DEBUG["summary"])
        exit_code = 1
    else:
        debug_print("Only outcome is passed (or none), exit with code 0",
                    DEBUG["summary"])
        exit_code = 0

    if DEBUG["verify"]:
        debug_print("Saved Results (dictionaries)", DEBUG["verify"])
        for i, res in enumerate(SessionStatus.verifications.saved_results):
            debug_print("{} - {}".format(i, res.__dict__), DEBUG["verify"])
        debug_print("Saved Tracebacks (dictionaries)", DEBUG["verify"])
        for i, tb in enumerate(SessionStatus.verifications.saved_tracebacks):
            debug_print("{} - {}".format(i, tb.__dict__), DEBUG["verify"])
        for saved_tb in SessionStatus.verifications.saved_tracebacks:
            debug_print("Result {0.result_link} linked to traceback {0}"
                        .format(saved_tb), DEBUG["verify"])
    if DEBUG["summary"]:
        debug_print("Run order:", DEBUG["summary"])
        for module_class_function in SessionStatus.run_order:
            debug_print("{0[0]}::{0[1]}::{0[2]}".format(module_class_function),
                        DEBUG["summary"])
        debug_print("Test function fixture dependencies:", DEBUG["summary"])
        for test_name, setup_fixtures in SessionStatus.test_fixtures.items():
            debug_print("{} depends on setup fixtures: {}"
                        .format(test_name, ", ".join(setup_fixtures)),
                        DEBUG["summary"])
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

    # Parse the pytest reports
    # Extract report type, outcome, duration, when (phase), location (test
    # function). Session based reports (CollectReport, (pytest-)WarningReport)
    # are collated for printing.
    pytest_reports = terminalreporter.stats
    reports_total = sum(len(v) for k, v in list(pytest_reports.items()))
    debug_print("{} pytest reports".format(reports_total), DEBUG["summary"])
    collect_error_reports = []
    pytest_warning_reports = []
    for report_type, reports in pytest_reports.items():
        for report in reports:
            debug_print("Report type: {}, report: {}".format(
                report_type, report), DEBUG["summary"])
            if isinstance(report, CollectReport):
                debug_print("Found CollectReport", DEBUG["summary"])
                collect_error_reports.append(report)
            elif isinstance(report, WarningReport):
                debug_print("Found WarningReport", DEBUG["summary"])
                pytest_warning_reports.append(report)

    # Print the expected fail, unexpected pass and skip reports exactly as
    # pytest does.
    # FIXME is it possible to do this on the module basis? must be bexause I
    #  do update Mongo with xFail??
    lines = []
    show_xfailed(terminalreporter, lines)
    show_xpassed(terminalreporter, lines)
    show_skipped(terminalreporter, lines)

    # Print the reports of any collection errors or pytest-warnings (on
    # session basis as these are not related to specific tests) TODO check
    for report in collect_error_reports:
        lines.append("COLLECTION ERROR {}".format(report.longrepr))
    for report in pytest_warning_reports:
        lines.append("PYTEST-WARNING {} {}".format(report.nodeid,
                                                   report.message))
    if lines:
        LogLevel.high_level_step("collection error, skip, xFail/xPass and "
                                 "pytest-warning reasons (short test summary "
                                 "info)")
        for line in lines:
            LogLevel.detail_step(line)
        debug_print("Pytest warnings or collection errors reported, exit with "
                    "error code 1", DEBUG["summary"])
        exit_code = 1
    else:
        LogLevel.high_level_step("No collection errors, skips, xFail/xPass or "
                                 "pytest-warnings")
    # TODO update Mongo session and print to the session dashboard

    # session_duration = time.time() - terminalreporter._sessionstarttime

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
    if CONFIG["disable-exit-code"].value:
        exit(0)
    else:
        exit(exit_code)
    # TODO expand to have unique codes for each outcome type
    # TODO exit code can be used to inform jenkins if the test session
    # passed or failed (or warned)
    # print("Anything following this message is the original pytest code")


def _print_summary(terminalreporter, report):
    # print "********** {} **********".format(report)
    # writes directly - does not return anything
    getattr(terminalreporter, "summary_{}".format(report))()
