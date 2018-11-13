##
# @file outcomes.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin:outcomes -
from builtins import object


class Outcomes(object):
    setup_skip = "setup skipped"
    skip = "skipped"
    teardown_skip = "teardown skipped"
    error = "error"
    setup_error = "setup errored"
    fail = "failed"
    teardown_error = "teardown errored"
    warning = "warned"
    setup_warning = "setup warned"
    teardown_warning = "teardown warned"
    # TODO do these also need to be phase specific?
    expected_fail = "expected failure"
    unexpected_pass = "unexpectedly passed"
    passed = "passed"
    pytest_warning = "pytest-warning"
    collect_error = "collection error"
    unknown = "Unknown result"
    in_progress = "in-progress"
    pending = "pending"


phase_map = {
    Outcomes.skip: {"setup": Outcomes.setup_skip,
                    "teardown": Outcomes.teardown_skip},
    Outcomes.fail: {"setup": Outcomes.setup_error,
                    "teardown": Outcomes.teardown_error},
    Outcomes.warning: {"setup": Outcomes.setup_warning,
                       "teardown": Outcomes.teardown_warning},
    Outcomes.error: {"setup": Outcomes.setup_error,
                     "teardown": Outcomes.teardown_error},
}


def phase_specific_result(phase, result):
    try:
        return phase_map[result][phase]
    except KeyError:
        return result


def plural(outcome):
    if outcome in _plurals:
        return _plurals[outcome]
    else:
        # no plural version required
        return outcome


# TODO where does unknown fit in here?
hierarchy = (
    Outcomes.setup_skip,
    Outcomes.skip,
    Outcomes.teardown_skip,
    Outcomes.error,
    Outcomes.setup_error,
    Outcomes.fail,
    Outcomes.teardown_error,
    Outcomes.warning,
    Outcomes.setup_warning,
    Outcomes.teardown_warning,
    Outcomes.expected_fail,
    Outcomes.unexpected_pass,
    Outcomes.passed,
    Outcomes.pytest_warning,
    Outcomes.collect_error,
    Outcomes.unknown,
    Outcomes.in_progress,
    Outcomes.pending
    # TODO what about call phases that aren't run?
)

_plurals = {
    Outcomes.setup_skip: "setups skipped",
    Outcomes.teardown_skip: "teardowns skipped",
    Outcomes.setup_error: "setups errored",
    Outcomes.teardown_error: "teardowns errored",
    Outcomes.setup_warning: "setups warned",
    Outcomes.teardown_warning: "teardowns warned",
    Outcomes.expected_fail: "expected failures",
    # Outcomes.unexpected_pass: "unexpectedly passed",
    Outcomes.pytest_warning: "pytest-warning",
    Outcomes.collect_error: "collection error"
}

# this list is hierarchical so order is important
outcome_conditionals = (
    (lambda summary, pytest_result: pytest_result == "skipped",
     Outcomes.skip),
    (lambda summary, pytest_result: pytest_result == "xfailed",
     Outcomes.expected_fail),
    (lambda summary, pytest_result: pytest_result == "xpassed",
     Outcomes.unexpected_pass),
    (lambda summary, pytest_result:
     True in [x in list(summary.keys()) for x in ("A", "O", "F")],
     Outcomes.fail),
    (lambda summary, pytest_result:
     True in ["W" in list(summary.keys())],
     Outcomes.warning),
    (lambda summary, pytest_result: pytest_result == "error",
     Outcomes.error),
    (lambda summary, pytest_result: pytest_result == "failed",
     Outcomes.fail),
    (lambda summary, pytest_result: True,
     Outcomes.passed)
)

# TODO add skip and xfail
fixture_outcome_conditionals = (
    (lambda s: "S" in list(s.keys()),
     Outcomes.skip),
    (lambda s: "X" in list(s.keys()),
     Outcomes.expected_fail),
    (lambda s: True in [x in list(s.keys()) for x in ("A", "O", "F")],
     Outcomes.fail),
    (lambda s: True in ["W" in list(s.keys())],
     Outcomes.warning),
    (lambda s: True,
     Outcomes.passed)
)
