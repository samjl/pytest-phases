##
# @file verify.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin:verify
# Verification functionality and saving of test session results,
# session state tracking (current phase, module, class, fixture, test function)

import inspect
import pytest
import re
import sys
from collections import OrderedDict
from future.utils import raise_

from _pytest.fixtures import FixtureDef  # requires pytest version>=3.0.0

from common import (
    CONFIG,
    DEBUG,
    debug_print
)
from loglevels import (
    get_current_l1_msg,
    get_current_level
)

# TODO The traceback depth set here is just an arbitrary figure and could be
# user configurable up to the maximum (1000?).
MAX_TRACEBACK_DEPTH = 20


class WarningException(Exception):
    pass


class VerificationException(Exception):
    pass


class SessionStatus(object):
    # Track the session status
    phase = None  # Current test phase: setup, call, teardown
    run_order = []  # Test execution order contains tuples of parent,
    # test function
    test_fixtures = OrderedDict()  # Test function: list of fixtures
    test_function = None  # Currently active test - set at beginning of setup

    exec_func_fix = None  # Currently executing setup fixture or test function
    active_setups = []

    module = None
    class_name = None
    session = None


class Verifications:
    # Module level storage of verification results and tracebacks for
    # failures and warnings.
    saved_tracebacks = []
    saved_results = []


class Result(object):
    """Object used to save a result of the verify function or
    any other caught exceptions.
    """
    def __init__(self, message, status, type_code, scope, source_function,
                 source_code, raise_immediately, source_locals=None,
                 fail_traceback_link=None):
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
        if self.phase == "teardown":
            self.fixture_name = SessionStatus.active_setups[-1]
        else:
            self.fixture_name = SessionStatus.exec_func_fix

        # Additional attributes for keeping track of the result
        # FIXME currently not used
        self.printed = False

    def formatted_dict(self):
        # TODO add session
        f = OrderedDict()
        f["Step"] = self.step
        f["Message"] = self.msg
        f["Status"] = self.status
        if DEBUG["summary"]:
            f["Class"] = self.class_name
            f["Module"] = self.module
            f["Phase"] = self.phase
            f["Scope"] = self.scope
            f["Source Fixture/Function"] = self.fixture_name
            f["Test Function"] = self.test_function
            f["ID"] = hex(id(self))[-4:]
            f["Tb ID"] = hex(id(self.traceback_link))[-4:] if \
                self.traceback_link else None
            if self.traceback_link:
                raised = "Y" if self.traceback_link.raised else "N"
            else:
                raised = "-"
            e = "{}.{}.{}.{}".format(self.type_code,
                                     "Y" if self.raise_immediately else "N",
                                     "Y" if self.printed else "N",
                                     raised)
            f["Extra"] = e
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

    debug_print("Performing verification", DEBUG["verify"])
    debug_print("Locals: {}".format(inspect.getargvalues(inspect.stack()[1][0]).locals),
                DEBUG["verify"])

    def warning_init():
        debug_print("WARNING (fail_condition)", DEBUG["verify"])
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
        debug_print("Length of stack = {}".format(len(stack)),
                    DEBUG["verify"])
        max_traceback_depth = MAX_TRACEBACK_DEPTH
    else:
        max_traceback_depth = len(stack)

    for depth in range(start_depth, max_traceback_depth):  # Already got 3
        calling_func = _get_calling_func(stack, depth, stop_at_test,
                                         full_method_trace)
        if calling_func:
            source_function, source_locals, source_call = calling_func
            tb_new = [source_function]
            if source_locals:
                tb_new.append(source_locals)
            tb_new.extend(source_call)
            tb[0:0] = tb_new
        else:
            # FIXME
            break
    return tb


def _get_calling_func(stack, depth, stop_at_test, full_method_trace):
    calling_source = []
    try:
        func_source = inspect.getsourcelines(stack[depth][0])
    except Exception as e:
        debug_print("{}".format(str(e)), DEBUG["verify"])
        return
    else:
        func_line_number = func_source[1]
        func_call_source_line = "{0[4][0]}".format(stack[depth])
        if stop_at_test and trace_end_detected(func_call_source_line.strip()):
            return
        call_line_number = stack[depth][2]
        module_line_parent = "{0[1]}:{0[2]}:{0[3]}".format(stack[depth])
        calling_frame_locals = ""
        if CONFIG["include-verify-local-vars"].value\
                or CONFIG["include-all-local-vars"].value:
            try:
                # args = inspect.getargvalues(stack[depth][0]).locals.items()
                # calling_frame_locals = (", ".join("{}: {}".format(k, v)
                #                         for k, v in args))
                calling_frame_locals = dict(inspect.getargvalues(stack[depth]
                                            [0]).locals.items())
            except Exception as e:
                pytest.log.step("Failed to retrieve local variables for {}".
                                format(module_line_parent), log_level=5)
                debug_print("{}".format(str(e)), DEBUG["verify"])
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
    # TODO update this
    """Save a result of verify/_verify.
    Items to save:
    Saved result - Step,
                   Message,
                   Status,
                   Extra Info (instance of ResultInfo)
    Traceback - type,
                tb,
                complete,
                raised,
                res_index
    """
    stack = inspect.stack()
    depth = 3

    debug_print("Saving a result of verify function", DEBUG["verify"])
    fixture_name = None
    fixture_scope = None
    if SessionStatus.phase != "call":
        for d in range(depth, depth+6):  # TODO use max tb depth?
            # frame = stack[d][0]
            stack_locals = OrderedDict(inspect.getargvalues(stack[d][0]).
                                       locals.items())
            for item in stack_locals.values():
                # print item
                if isinstance(item, FixtureDef):
                    fixture_name = item.argname
                    fixture_scope = item.scope
                    debug_print("scope for {} is {} [{}]".format(fixture_name,
                                                                 fixture_scope, d), DEBUG["verify"])
            if fixture_scope:
                break

    # TODO check performance of this - not sure if we want to do it for all
    source_function, source_locals, source_call = \
        _get_calling_func(stack, depth, True, full_method_trace)
    tb_depth_1 = [source_function]
    if source_locals:
        tb_depth_1.append(source_locals)
    tb_depth_1.extend(source_call)

    depth += 1
    s_res = Verifications.saved_results
    type_code = status[0]
    if type_code == "F" or type_code == "W":
        # Types processed by this function are "P", "F" and "W"
        trace_complete = _get_complete_traceback(stack, depth, stop_at_test,
                                                 full_method_trace,
                                                 tb=tb_depth_1)

        s_tb = Verifications.saved_tracebacks
        s_tb.append(FailureTraceback(exc_type, exc_tb, trace_complete))
        failure_traceback = s_tb[-1]
    else:
        failure_traceback = None
    s_res.append(Result(msg, status, type_code, fixture_scope,
                        source_function, source_call, raise_immediately,
                        source_locals=source_locals,
                        fail_traceback_link=failure_traceback))
    if type_code == "F" or type_code == "W":
        s_tb[-1].result_link = s_res[-1]


def set_saved_raised():
    # Set saved traceback as raised so they are not subsequently raised
    # again.
    for saved_traceback in Verifications.saved_tracebacks:
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


def print_saved_results(column_key_order="Step", extra_info=False):
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
    debug_print("Column order: {}".format(column_key_order),
                DEBUG["print-saved"])

    to_print = []
    for saved_result in Verifications.saved_results:
        to_print.append(saved_result.formatted_dict())

    key_val_lengths = {}
    if len(to_print) > 0:
        _get_val_lengths(to_print, key_val_lengths)
        headings = _get_key_lengths(key_val_lengths)
        pytest.log.high_level_step("Saved results")
        _print_headings(to_print[0], headings, key_val_lengths,
                        column_key_order)
        for result in to_print:
            _print_result(result, key_val_lengths, column_key_order)
        print "Extra fields: raise_immediately.printed.raised"


def _print_result(result, key_val_lengths, column_key_order):
    # Print a table row for a single saved result.
    line = ""
    for key in column_key_order:
        # Print values in the order defined by column_key_order.
        length = key_val_lengths[key]
        line += '| {0:^{1}} '.format(str(result[key]), length)
    for key in result.keys():
        key = key.strip()
        if key not in column_key_order:
            length = key_val_lengths[key]
            if key == "Extra Info":
                val = result[key].format_result_info()
            else:
                val = result[key]
            line += '| {0:^{width}} '.format(str(val), width=length)
    line += "|"
    # line += "| {}".format(i)
    # pytest.log.detail_step(line)
    # DEBUG
    print line
    # print result["Extra Info"].source_function
    # for line in result["Extra Info"].source_call:
    #     print line
    # DEBUG END


def _get_val_lengths(saved_results, key_val_lengths):
    # Update the maximum field length dictionary based on the length of
    # the values.
    for result in saved_results:
        for key, value in result.items():
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
    for key, val in key_val_lengths.iteritems():
        debug_print("key: {}, key length: {}, length of field from values "
                     "{}".format(key, len(key), val), DEBUG["print-saved"])
        if len(key) > val:
            # The key is longer then the value length
            if ' ' in key or '/' in key:
                # key can be split up to create multi-line heading
                space_indices = [m.start() for m in re.finditer(' ', key)]
                slash_indices = [m.start() for m in re.finditer('/', key)]
                space_indices.extend(slash_indices)
                debug_print("key can be split @ {}".format(space_indices),
                            DEBUG["print-saved"])
                key_centre_index = int(len(key)/2)
                split_index = min(space_indices, key=lambda x: abs(
                    x - key_centre_index))
                debug_print('The closest index to the middle ({}) is {}'
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
    print "_" * line_length  # DEBUG
    for key in column_key_order:
        field_length = key_val_lengths[key]
        for line_index in (0, 1):
            lines[line_index] += '| ' + '{0:^{width}}'.format(
                headings[key][line_index], width=field_length) + ' '
        lines[2] += '|-' + '-'*field_length + '-'
    for key, value in first_result.items():
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
        print line
