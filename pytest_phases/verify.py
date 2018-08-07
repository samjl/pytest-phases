##
# @file verify.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin:verify
# Verification functionality and saving of test session results,
# session state tracking (current phase, module, class, fixture, test function)
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
import inspect
import pytest
import re
import sys
from _pytest.fixtures import FixtureDef  # requires pytest version>=3.0.0
from builtins import object, range, str
from collections import OrderedDict
from future.utils import raise_
from past.utils import old_div
from .common import (
    CONFIG,
    DEBUG
)
from .common import debug_print as debug_print_common
from .loglevels import (
    get_current_l1_msg,
    get_current_level
)
from .outcomes import (
    fixture_outcome_conditionals,
    outcome_conditionals,
    phase_specific_result
)

# TODO The traceback depth set here is just an arbitrary figure and could be
# user configurable up to the maximum (1000?).
MAX_TRACEBACK_DEPTH = 20


def debug_print(msg, prettify=None):
    debug_print_common(msg, DEBUG["verify"], prettify)


class WarningException(Exception):
    pass


class VerificationException(Exception):
    pass


class Verifications(object):
    @classmethod
    def _results_summary(cls, results):
        summary = {}
        for result in results:
            if result.type_code not in summary:
                summary[result.type_code] = 1
            else:
                summary[result.type_code] += 1
        return summary

    @classmethod
    def _raise_exc_type(cls, results, type_to_raise):
        for i, saved_result in enumerate(results):
            if saved_result.traceback_link:
                exc_type = saved_result.traceback_link.exc_type
                debug_print("saved traceback index: {}, type: {}, "
                            "searching for: {}".format(i, exc_type,
                                                       type_to_raise),
                            DEBUG["verify"])
                if (exc_type == type_to_raise and not
                        saved_result.traceback_link.raised):
                    msg = "{0.msg} - {0.status}".format(saved_result)
                    tb = saved_result.traceback_link.exc_traceback
                    debug_print("Re-raising first saved {}: {} {} {}"
                                .format(type_to_raise, exc_type, msg, tb))
                    set_saved_raised()  # FIXME is this required?
                    # for python 2 and 3 compatibility
                    raise_(exc_type, msg, tb)

    def __init__(self):
        self.saved_tracebacks = []
        self.saved_results = []

    # Raise any saved VerificationExceptions over WarningExceptions
    # Any other exceptions have already been raised (and saved when caught in
    # pytest_fixture_setup).
    def fixture_setup_raise_saved(self, fixture_name, test_name):
        results = self._fixture_setup_results(fixture_name, test_name)
        self._raise_exc_type(results, VerificationException)
        self._raise_exc_type(results, WarningException)

    def fixture_teardown_raise_saved(self, fixture_name, test_name):
        results = self._fixture_teardown_results(fixture_name, test_name)
        self._raise_exc_type(results, VerificationException)
        self._raise_exc_type(results, WarningException)

    def _fixture_setup_results(self, fixture_name, test_name):
        results = self._fixture_results("setup", fixture_name, test_name)
        summary = self._results_summary(results)
        debug_print("{} results summary:".format(fixture_name),
                    prettify=summary)

        def fixture_outcome(saved_summary):
            for outcome_condition, outcome in fixture_outcome_conditionals:
                if outcome_condition(saved_summary):
                    return phase_specific_result("setup", outcome)

        debug_print("{} setup outcome: {}".format(fixture_name,
                                                  fixture_outcome(summary)))
        return results

    def _fixture_teardown_results(self, fixture_name, test_name):
        results = self._fixture_results("teardown", fixture_name, test_name)
        summary = self._results_summary(results)
        debug_print("{} results summary:".format(fixture_name),
                    prettify=summary)

        def fixture_outcome(saved_summary):
            for outcome_condition, outcome in fixture_outcome_conditionals:
                if outcome_condition(saved_summary):
                    return phase_specific_result("teardown", outcome)

        debug_print("{} teardown outcome: {}".format(fixture_name,
                                                     fixture_outcome(summary)))
        return results

    def _fixture_results(self, phase, fixture_name, test_name):
        return self.filter_results(phase=phase, fixture_name=fixture_name,
                                   test_function=test_name)

    def phase_summary_and_outcome(self, phase, result_category):
        results = self.phase_results(phase)
        summary = self._results_summary(results)
        debug_print("{} results summary:".format(phase.capitalize()),
                    prettify=summary)

        def phase_outcome(saved_summary, pytest_outcome):
            for outcome_condition, outcome in outcome_conditionals:
                if outcome_condition(saved_summary, pytest_outcome):
                    return phase_specific_result(phase, outcome)

        debug_print("{} outcome: {}".format(
            phase.capitalize(), phase_outcome(summary, result_category)
        ))

    def phase_results(self, phase):
        test = SessionStatus.test_function
        if phase == "call":
            # call only
            results = self.filter_results(phase=phase, test_function=test)
        else:
            # module scope fixtures filter
            module = SessionStatus.module
            results = self.filter_results(phase=phase, scope="module",
                                          module_name=module)
            if SessionStatus.class_name:
                # class scope fixtures filter
                class_name = SessionStatus.class_name
                results.extend(self.filter_results(phase=phase, scope="class",
                                                   class_name=class_name))
            # function scope fixtures filter
            results.extend(self.filter_results(phase=phase, scope="function",
                                               test_function=test))
        return results

    def filter_results(self, test_function=None, phase=None, scope=None,
                       fixture_name=None, class_name=None, module_name=None):
        # DEBUG
        local_vars = inspect.getargvalues(inspect.currentframe())[-1]
        params = ["{}:{}".format(k, v) for k, v in local_vars.items() if v is
                  not None and k != "self"]
        debug_print("Filter params:", prettify=params)
        # TODO assert if all parameters are None
        filtered = []
        for res in self.saved_results:
            if phase:
                if res.phase != phase:
                    continue
            if scope:
                if res.scope != scope:
                    continue
            if test_function:
                if res.test_function != test_function:
                    continue
            if fixture_name:
                if res.fixture_name != fixture_name:
                    continue
            if class_name:
                if res.class_name != class_name:
                    continue
            if module_name:
                if res.module != module_name:
                    continue
            filtered.append(res)
        debug_print("Filtered results:", prettify=filtered)
        return filtered


class SessionStatus(object):
    # Track the session status
    phase = None  # Current test phase: setup, call, teardown
    run_order = []  # Test execution order contains tuples of parents and
    # tests e.g. module, class, test
    test_function = None  # Currently active test - set at beginning of setup
    test_fixtures = OrderedDict()  # Test function: list of fixtures per test
    exec_func_fix = None  # Currently executing setup fixture or test function
    active_setups = []  # The setup fixtures currently active (haven't been
    # torn down yet)
    module = None  # Parent module of current test
    class_name = None  # Parent class of current test if applicable
    prev_teardown = None  # Track the most recently completed teardown
    # fixture so it can be assigned to any regular assertions raised

    # MongoDB
    mongo = None
    test_object_id = None  # Same as mongo.test_oid

    verifications = Verifications()


class Result(object):
    """Object used to save a result of the verify function or
    any other caught exceptions.
    """
    def __init__(self, message, status, type_code, scope, source_function,
                 source_code, raise_immediately, source_locals=None,
                 # fail_traceback_link=None, td=None):
                 fail_traceback_link=None, use_prev_teardown=False):
        # Basic result information
        self.step = get_current_l1_msg()
        self.msg = message
        self.status = status

        # Additional result information
        # Type codes:
        # "P": pass, "W": WarningException, "F": VerificationException
        # "A": AssertionError, "O": any Other exception
        self.type_code = type_code
        self.source = {
            "module-function-line": source_function,
            "code": source_code,
            "locals": source_locals
        }
        # Link to the saved traceback object for failures
        self.traceback_link = fail_traceback_link
        self.raise_immediately = raise_immediately

        # Information about source of the result
        # self.session = SessionStatus.session  # Required?
        self.class_name = SessionStatus.class_name
        self.module = SessionStatus.module
        self.phase = SessionStatus.phase
        self.scope = scope
        self.test_function = SessionStatus.test_function
        if use_prev_teardown:
            # required to track regular assertions raised during teardown
            self.fixture_name = SessionStatus.prev_teardown
        elif self.phase == "teardown":
            # workaround for intermediate (parameterized) module teardown
            # pytest bug https://github.com/pytest-dev/pytest/issues/3032
            self.fixture_name = SessionStatus.active_setups[-1]
        else:
            self.fixture_name = SessionStatus.exec_func_fix

        # DEBUG ONLY
        self.active = list(SessionStatus.active_setups)

    def formatted_dict(self):
        # TODO add session
        f = OrderedDict()
        f["Step"] = self.step
        f["Message"] = self.msg
        f["Status"] = self.status
        if DEBUG["summary"]:
            f["Class"] = self.class_name
            f["Module"] = self.module.split("/")[-1]
            f["Phase"] = self.phase
            f["Scope"] = self.scope
            f["Source Fixture/Function"] = self.fixture_name
            f["Test Function"] = self.test_function
            f["Active Setups"] = ",".join(self.active)
            f["ID"] = hex(id(self))[-4:]
            # f["Tb ID"] = hex(id(self.traceback_link))[-4:] if \
            #     self.traceback_link else None
            # if self.traceback_link:
            #     raised = "Y" if self.traceback_link.raised else "N"
            # else:
            #     raised = "-"
            # e = "{}.{}.{}".format(self.type_code,
            #                       "Y" if self.raise_immediately else "N",
            #                       raised)
            # f["Extra"] = e
        return f


class FailureTraceback(object):
    """Object used to store the traceback information for a failure or
    warning result.
    """
    def __init__(self, exc_type, exc_traceback, formatted_traceback,
                 raised=False):
        self.exc_type = exc_type
        self.exc_traceback = exc_traceback
        # Processed version of the traceback starting at the call to verify
        # (not where the exception is caught an re-raised).
        self.formatted_traceback = formatted_traceback
        self.raised = raised
        self.result_link = None


def perform_verification(fail_condition, fail_message, raise_immediately,
                         warning, warn_condition, warn_message,
                         full_method_trace, stop_at_test, log_level):
    """Perform a verification of a given condition using the parameters
    provided.
    """
    if warning:
        raise_immediately = False

    debug_print("Performing verification")
    debug_print("Locals: {}".format(inspect.getargvalues(inspect.stack()[1][0]).locals))

    def warning_init():
        debug_print("WARNING (fail_condition)")
        try:
            raise WarningException()
        except WarningException:
            traceback = sys.exc_info()[2]
        return "WARNING", WarningException, traceback

    def failure_init():
        try:
            raise VerificationException()
        except VerificationException:
            traceback = sys.exc_info()[2]
        return "FAIL", VerificationException, traceback

    def pass_init():
        return "PASS", None, None

    if not fail_condition:
        msg = fail_message
        if warning:
            status, exc_type, exc_tb = warning_init()
        else:
            status, exc_type, exc_tb = failure_init()
    elif warn_condition is not None:
        if not warn_condition:
            status, exc_type, exc_tb = warning_init()
            msg = warn_message
        else:
            # Passed
            status, exc_type, exc_tb = pass_init()
            msg = fail_message
    else:
        # Passed
        status, exc_type, exc_tb = pass_init()
        msg = fail_message

    if not log_level and get_current_level() == 1:
        verify_msg_log_level = 2
    else:
        verify_msg_log_level = log_level
    pytest.log.step("{} - {}".format(msg, status), verify_msg_log_level)
    _save_result(msg, status, exc_type, exc_tb, stop_at_test,
                 full_method_trace, raise_immediately)

    if not fail_condition and raise_immediately:
        # Raise immediately
        set_saved_raised()
        raise_(exc_type, msg, exc_tb)
    return True


def _get_complete_traceback(stack, start_depth, stop_at_test,
                            full_method_trace, tb=[]):
    # Print call lines or source code back to beginning of each calling
    # function (fullMethodTrace).
    if len(stack) > MAX_TRACEBACK_DEPTH:
        debug_print("Length of stack = {}".format(len(stack)))
        max_traceback_depth = MAX_TRACEBACK_DEPTH
    else:
        max_traceback_depth = len(stack)

    for depth in range(start_depth, max_traceback_depth):  # Already got 3
        calling_func = _get_calling_func(stack, depth, stop_at_test,
                                         full_method_trace)
        if calling_func:
            source_function, source_locals, source_call = calling_func
            tb_new = dict(
                location=source_function,
                locals=source_locals,
                code=source_call
            )
            tb.insert(0, tb_new)
        else:
            # Failed to retrieve calling traceback
            break  # FIXME should this be continue?
    return tb


def _get_calling_func(stack, depth, stop_at_test, full_method_trace):
    calling_source = []
    try:
        func_source = inspect.getsourcelines(stack[depth][0])
    except Exception as e:
        debug_print("{}".format(str(e)))
        return
    else:
        func_line_number = func_source[1]
        func_call_source_line = "{0[4][0]}".format(stack[depth])
        if stop_at_test and trace_end_detected(func_call_source_line.strip()):
            return
        call_line_number = stack[depth][2]
        module_line_parent = "{0[1]}:{0[2]}:{0[3]}".format(stack[depth])
        calling_frame_locals = {}
        if CONFIG["include-verify-local-vars"].value\
                or CONFIG["include-all-local-vars"].value:
            try:
                # args = inspect.getargvalues(stack[depth][0]).locals.items()
                # calling_frame_locals = (", ".join("{}: {}".format(k, v)
                #                         for k, v in args))
                calling_frame_locals = dict(list(inspect.getargvalues(stack[depth]
                                            [0]).locals.items()))
            except Exception as e:
                pytest.log.step("Failed to retrieve local variables for {}".
                                format(module_line_parent), log_level=5)
                debug_print("{}".format(str(e)))
        if full_method_trace:
            for lineNumber in range(0, call_line_number - func_line_number):
                source_line = re.sub('[\r\n]', '', func_source[0][lineNumber])
                calling_source.append(source_line)
            source_line = re.sub('[\r\n]', '', func_source[0][
                call_line_number-func_line_number][1:])
            calling_source.append(">{}".format(source_line))
        else:
            calling_source = _get_call_source(func_source,
                                              func_call_source_line,
                                              call_line_number,
                                              func_line_number)
        return module_line_parent, calling_frame_locals, calling_source


# TODO modify this so the traceback goes back far enough to detect the scope
def trace_end_detected(func_call_line):
    # Check for the stop keywords in the function call source line
    # (traceback). Returns True if keyword found and traceback is
    # complete, False otherwise.
    # func_call_line.strip()
    if not func_call_line:
        return False
    stop_keywords = ("runTest", "testfunction", "fixturefunc")
    return any(item in func_call_line for item in stop_keywords)


def _save_result(msg, status, exc_type, exc_tb, stop_at_test,
                 full_method_trace, raise_immediately):
    """Save a result of verify/_verify.
    Items to save:
    Result object for all results, plus FailureTraceback object for results
    other than pass.
    """
    stack = inspect.stack()
    depth = 3

    debug_print("Saving a result of verify function")
    fixture_name = None
    fixture_scope = None
    if SessionStatus.phase != "call":
        for d in range(depth, depth+6):  # TODO use max tb depth?
            # For setup and teardown phases (in fixture), parse locals in
            # stack to extract the fixture name and scope
            # Locals for current frame
            stack_locals = OrderedDict(list(inspect.getargvalues(stack[d][0]).
                                       locals.items()))
            for item in list(stack_locals.values()):
                if isinstance(item, FixtureDef):
                    fixture_name = item.argname
                    fixture_scope = item.scope
                    debug_print("scope for {} is {} [{}]".format(fixture_name,
                                                                 fixture_scope,
                                                                 d))
            if fixture_scope:
                break

    # Get the calling function and local vars for all results.
    # Don't really need to do this for all results, passes? so if
    # performance suffers this could be removed.
    source_function, source_locals, source_call = \
        _get_calling_func(stack, depth, True, full_method_trace)
    tb_depth_1 = [source_function]
    if source_locals:
        tb_depth_1.append(source_locals)
    tb_depth_1.extend(source_call)

    trace_complete = [dict(
        location=source_function,
        locals=source_locals,
        code=source_call
    )]
    depth += 1
    s_res = SessionStatus.verifications.saved_results
    type_code = status[0]
    if type_code == "F" or type_code == "W":
        # Types processed by this function are "P", "F" and "W"
        trace_complete = _get_complete_traceback(stack, depth, stop_at_test,
                                                 full_method_trace,
                                                 tb=trace_complete)

        s_tb = SessionStatus.verifications.saved_tracebacks
        s_tb.append(FailureTraceback(exc_type, exc_tb, trace_complete))
        failure_traceback = s_tb[-1]
    else:
        failure_traceback = None
    result = Result(msg, status, type_code, fixture_scope,
                    source_function, source_call, raise_immediately,
                    source_locals=source_locals,
                    fail_traceback_link=failure_traceback)
    s_res.append(result)
    SessionStatus.mongo.insert_verification(result)
    if type_code == "F" or type_code == "W":
        s_tb[-1].result_link = s_res[-1]


def set_saved_raised():
    # Set saved traceback as raised so they are not subsequently raised
    # again.
    for saved_traceback in SessionStatus.verifications.saved_tracebacks:
        saved_traceback.raised = True


def _get_call_source(func_source, func_call_source_line, call_line_number,
                     func_line_number):
    trace_level = []
    # Check if the source line parentheses match (equal
    # number of "(" and ")" characters)
    left = 0
    right = 0

    def _parentheses_count(left, right, line):
        left += line.count("(")
        right += line.count(")")
        return left, right
    left, right = _parentheses_count(left, right,
                                     func_call_source_line)
    preceding_line_index = call_line_number - func_line_number - 1

    while left != right and preceding_line_index > call_line_number - func_line_number - 10:
        source_line = re.sub('[\r\n]', '', func_source[0][preceding_line_index])
        trace_level.insert(0, source_line)
        left, right = _parentheses_count(left, right,
                                         func_source[0][preceding_line_index])
        preceding_line_index -= 1

    source_line = re.sub('[\r\n]', '', func_call_source_line[1:])
    trace_level.append(">{}".format(source_line))
    return trace_level


def print_saved_results(column_key_order="Step"):
    """Format the saved results as a table and print.
    The results are printed in the order they were saved.
    Keyword arguments:
    column_key_order -- specify the column order. Default is to simply
    print the "Step" (top level message) first.
    extra_info -- print an extra column containing the "Extra Info" field
    values.
    """
    if not isinstance(column_key_order, (tuple, list)):
        column_key_order = [column_key_order]
    debug_print_common("Column order: {}".format(column_key_order),
                       DEBUG["print-saved"])

    to_print = []
    tb_links = []
    for saved_result in SessionStatus.verifications.saved_results:
        to_print.append(saved_result.formatted_dict())
        tb_links.append(saved_result.traceback_link)

    key_val_lengths = {}
    if len(to_print) > 0:
        _get_val_lengths(to_print, key_val_lengths)
        headings = _get_key_lengths(key_val_lengths)
        pytest.log.high_level_step("Saved results")
        _print_headings(to_print[0], headings, key_val_lengths,
                        column_key_order)
        for i, result in enumerate(to_print):
            _print_result(result, tb_links[i], key_val_lengths,
                          column_key_order)


def _print_result(result, traceback, key_val_lengths, column_key_order):
    # Print a table row at log level 2 for a single saved result.
    line = ""
    for key in column_key_order:
        # Print values in the order defined by column_key_order.
        length = key_val_lengths[key]
        line += '| {0:^{1}} '.format(str(result[key]), length)
    for key in list(result.keys()):
        key = key.strip()
        if key not in column_key_order:
            length = key_val_lengths[key]
            val = result[key]
            line += '| {0:^{width}} '.format(str(val), width=length)
    line += "|"
    pytest.log.detail_step(line)
    # If result has a linked traceback object then print it at log level 3.
    if traceback:
        for level in traceback.formatted_traceback:
            pytest.log.step(level['location'], log_level=3)
            if level['locals']:
                local_vars = ["{}: {}".format(k, v) for k, v in level[
                    'locals'].items() if not k.startswith("@py_")]
                pytest.log.step(", ".join(local_vars), log_level=3)
            pytest.log.step("\n".join(level['code']), log_level=3)
        pytest.log.step("{}: {}".format(traceback.exc_type.__name__,
                                        traceback.result_link.msg),
                        log_level=3)


def _get_val_lengths(saved_results, key_val_lengths):
    # Update the maximum field length dictionary based on the length of
    # the values.
    for result in saved_results:
        for key, value in list(result.items()):
            key = key.strip()
            if key not in key_val_lengths:
                key_val_lengths[key] = 0
            if key == "Extra Info":
                length = max(key_val_lengths[key],
                             len(str(value.format_result_info())))
            else:
                length = max(key_val_lengths[key], len(str(value)))
            key_val_lengths[key] = length


def _get_key_lengths(key_val_lengths):
    # Compare the key lengths to the max length of the corresponding
    # value.

    # Dictionary to store the keys (spilt if required) that form the
    # table headings.
    headings = {}
    for key, val in key_val_lengths.items():
        debug_print_common("key: {}, key length: {}, length of field from "
                           "values {}".format(key, len(key), val),
                           DEBUG["print-saved"])
        if len(key) > val:
            # The key is longer then the value length
            if ' ' in key or '/' in key:
                # key can be split up to create multi-line heading
                space_indices = [m.start() for m in re.finditer(' ', key)]
                slash_indices = [m.start() for m in re.finditer('/', key)]
                space_indices.extend(slash_indices)
                debug_print_common("key can be split @ {}".format(
                    space_indices), DEBUG["print-saved"])
                key_centre_index = int(old_div(len(key),2))
                split_index = min(space_indices, key=lambda x: abs(
                    x - key_centre_index))
                debug_print_common('The closest index to the middle ({}) is {}'
                                   .format(key_centre_index, split_index),
                                   DEBUG["print-saved"])
                # Add the split key string as two strings (line 1, line
                # 2) to the headings dictionary.
                headings[key] = [key[:split_index+1].strip(),
                                 key[split_index+1:]]
                # Update the lengths dictionary with the shortened
                # headings (The max length of the two lines)
                key_val_lengths[key] = max(len(headings[key][0]),
                                           len(headings[key][1]),
                                           key_val_lengths[key])
            # and can't be split
            else:
                key_val_lengths[key] = max(len(key), key_val_lengths[key])
                headings[key] = [key, ""]
        else:
            key_val_lengths[key] = max(len(key), key_val_lengths[key])
            headings[key] = [key, ""]

    return headings


def _get_line_length(key_val_lengths):
    # Return the line length based upon the max key/value lengths of
    # the saved results.
    line_length = 0
    # Calculate the line length (max length of all keys/values)
    for key in key_val_lengths:
        line_length += key_val_lengths[key] + 3
    line_length += 1
    return line_length


def _print_headings(first_result, headings, key_val_lengths,
                    column_key_order):
    # Print the headings of the saved results table (keys of
    # dictionaries stored in saved_results).
    lines = ["", "", ""]
    line_length = _get_line_length(key_val_lengths)
    # pytest.log.detail_step("_" * line_length)
    print("_" * line_length)  # DEBUG
    for key in column_key_order:
        field_length = key_val_lengths[key]
        for line_index in (0, 1):
            lines[line_index] += '| ' + '{0:^{width}}'.format(
                headings[key][line_index], width=field_length) + ' '
        lines[2] += '|-' + '-'*field_length + '-'
    for key, value in list(first_result.items()):
        key = key.strip()
        if not (((type(column_key_order) is list) and
                 (key in column_key_order)) or
                ((type(column_key_order) is not list) and
                 (key == column_key_order))):
            field_length = key_val_lengths[key]
            for line_index in (0, 1):
                lines[line_index] += ('| ' + '{0:^{width}}'.format(
                    headings[key][line_index], width=field_length) + ' ')
            lines[2] += ('|-' + '-'*field_length + '-')
    for line in lines:
        line += "|"
        # pytest.log.detail_step(line)
        print(line)
