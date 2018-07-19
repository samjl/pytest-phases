# pytest-phases Plugin
## Table of Contents
[Running Tests](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#running-tests)

[pytest ini file](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#add-pytest-command-line-options-added-to-ini-file)

[Log Messages](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#)
- [High Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#highest-level-log-level-1)
- [Detail Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#detail-level-log-level-2)
- [Custom Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#other-log-levels)

[Verifications](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verifications)
- [verify function](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verify-function-format-and-options)
- [Basic Usage](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#basic-usage)
- [Warnings](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#raising-warnings)
- [Failure and Warning Conditions](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verifications-including-failure-and-warning-conditions)

[Plugin Configuration](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#plugin-configuration)
- [Verification Options](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verification-configuration-options)

[Current Limitations](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#current-limitations)

[Future Work](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#future-work)
- [Log Levels](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#log-levels)
- [Verifications](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verifications)

# Running Tests

    pytest -s -q --tb=no -p no:logging example_tests/test_class_scope.py

The command line options can also be added to the pytest ini file for the entire project as described in the following section.

# Add pytest command line options added to ini file

Add command line options to pytest.ini (in root of testing directory):

    [pytest]
    addopts = -s -q --tb=no -p no:logging
 
* -s disable capture
* -q decrease verbosity (only effect currently is removing the "=" chars from the summary line)
* --tb=no suppress pytest tracebacks

Currently the most important issue to avoid pytest raising Attribute error and occasional freezes.
May be a conflict between this and the logging plugin but not found the root cause yet. 
Related to [this](https://github.com/pytest-dev/pytest/issues/3099) pytest defect.
* -p no:logging disable the logging plugin

## Log Messages
### Highest level (log level 1)
Print a message at the highest log level (1)

    log.high_level_step("Very important test step 1")
which is then printed in the log output as

    1-1 High level step: Very important, first test step
The first 1 is the log level and the second 1 is the step of this log level.

Note: The "High level step" printing above is just for debug use and will be removed before release.    
   
A subsequent high level message is then printed as:
    
    1-2 High level step: Second test step
where the 2 indicates it is the second step at level 1.

### Detail Level (log level 2)
Print a message at log level 2

    log.detail_step("More detailed test step information")
output:

    2-1 Detail level step: More detailed test step information
    
### Other log levels
The step function prints at the current log level if the log_level parameter is not defined
    
    log.step("This will be the next step at the current log level")
output:    

    2-2 Detail level step: This will be the next step at the current log level
    
Specifying a log level using the step function:
    
    log.step("Specify the log level", log_level=3)
output:

    3-1 Step: Specify the log level

Increment the current log level and print the message (default increment is 1 but can be specified using the increment parameter):
    
    log.step_increment("Increment the log level")
    log.step("Another step at this incremented level")
output:

    4-1 Step inc: Increment the log level
    4-2 Step: Another step at this incremented level

## Verifications
### verify Function Format and Options

Function call format
```python
verify(fail_condition, fail_message, raise_immediately=True,
       warning=False, warn_condition=None, warn_message=None,
       full_method_trace=False, stop_at_test=True, log_level=None)
```

Verification options:
- fail_condition:
an expression that if it evaluates to False raises a VerificationException
(or WarningException is warning is set to True).
- fail_message:
a message describing the verification being performed (requires fail_condition to be defined).
- raise_immediately (optional, default True):
whether to raise an exception immediately upon failure (same behaviour as regular assert).
- warning (optional, default None):
raise the fail_condition as a WarningException rather than VerificationException.

Warning options:
- warn_condition (optional, default None):
if fail_condition evaluates to True test this condition for a warning (cannot be used in addition to warning parameter).
Raises WarningException if expression evaluates to False.
- warn_message:
a message describing the warning condition being verified (requires warn_condition to be defined).

Traceback options:
- full_method_trace (optional, default False):
print an extended traceback with the full source of each calling function.
- stop_at_test (optional, default True):
stop printing the traceback when test function is reached (don't descend in to pytest).
- log_level (optional, default None):
the log level to assign to the verification message.
By default the verification message the log level applied is that of the previous message +1.
After printing the verification message the previous log level is restored.

### Basic Usage

Import the verify function from the pytest namespace:
```python
from pytest import log, verify
```

Basic use in place of a regular assert statement. Behaviour is identical to assert,
the exception is raised immediately and the test is torn down and ended.
```python
# expected to pass:
x = True
verify(x is True, "Check something is true (passes)")
# expected to fail immediately and raise exception:
y = False
verify(y is True, "Check something is true (fails)")
```

Save but do not raise failed verification:
```python
verify(y is True, "Check something is true (fails)", raise_immediately=False)
```

### Raising Warnings
As above but set the warning optional argument to raise a failed verification as a warningException:
```python
verify(y is True, "Check something is true (warning)", warning=True)
```

### Verifications Including Failure and Warning Conditions
It is also possible to specify a failure condition (that is tested first) and
a warning condition that is tested only if the failure condition does not generate a failure.
Example illustrating a variable with three ranges of values that can create PASS,
FAIL and WARNING conditions:
```python
# Setup the verification so that:
# if x < 3 pass
# if 3 <= x <= 10 warns
# is x > 10 fails

# Pass
x = 1
verify(x <= 10, "Check x is less than or equal to 10",
       warn_condition=x < 3, warn_message="Check x is less than 3")
# Warning
y = 10
verify(y <= 10, "Check y is less than or equal to 10",
       warn_condition=y < 3, warn_message="Check y is less than 3")
# Fail
z = 10.1
verify(z <= 10, "Check z is less than or equal to 10",
       warn_condition=z < 3, warn_message="Check z is less than 3")
``` 
 
It is also possible to test a completely different object(s) for warning if the failure condition is not met,
e.g.
```python
x = True
y = False
verify(x is True, "test x is True (initial pass)",
       warn_condition=y is True,
       warn_message="test y is True (initial pass->warning)")
```

## Plugin Configuration
The plugin can be configured by editing the config.cfg file created when the plugin is installed.
(This is created within the site-packages/pytest-verify directory).
The options in the configuration file may also be overridden by specifying them in the command line. 

### Verification Configuration Options
- include-verify-local-vars (Boolean):
Include local variables in tracebacks created by verify function.
- include-all-local-vars (Boolean):
Include local variables in all tracebacks. Warning: Printing all locals in a stack trace can easily lead to problems due to errored output.
- traceback-stops-at-test-functions (Boolean):
Stop the traceback at the test function.
- raise-warnings (Boolean):
Raise warnings (enabled) or just save the result (disabled).
- continue-on-setup-failure (Boolean):
Continue to the test call phase if the setup fails.
- continue-on-setup-warning (Boolean):
Continue to the test call phase if the setup warns. To raise a setup warning this must be set to False and raise-warnings set to True.

Note: Boolean options may be entered as 1/yes/true/on or 0/no/false/off.

- maximum-traceback-depth (Integer):
Print up to the maximum limit (integer) of stack trace entries.

## Current Limitations
- failure/warning_message parameters expect a string rather than an expression
(assert condition prints result of an expression as the exception message).

## Future Work
### Log Levels
- Add function to print blocks of messages such as lists
- Add ability (via config flag) to continue to the call phase of the test if setup raises a warning (or failure)
- Add database support (log messages + status live updates)
- Choose type of exception to raise
- Add verify parameter to disable printing and saving the result if it is a passes
### Verifications
Complete results table: add traceback to rows that warn/fail

Highlight active setups and their status for each test function result

Update the pytest status line using the new information (e.g 1 setup-warning, 2 passes)

Enhancement: test to decide whether teardown is required if test passes
(useful when using the same function scoped setup for multiple test functions)

Enhancement: test may inspect previous test result to check if (function) setup is required.

Possible enhancement - configuration for each setup/teardown fixture: 
- continue-to-call: continue to the test function call phase regardless of the setup result
- no-setup-if-prev-pass/warn: don't setup again (function scope) is previous test passed or warned
- teardown-on-pass: whether to teardown or not is the test passes (setup and call)
- teardown-on-warning: whether to teardown or not based on warnings (in setup and call)  
- raise-setup/call/teardown-warnings: more fine grained scope control over raising warnings
