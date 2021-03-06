# pytest-phases Plugin
## Table of Contents
[Running Tests](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#running-tests)

[pytest ini file](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#add-pytest-command-line-options-added-to-ini-file)

[Log Messages](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#)
- [High Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#highest-level-log-level-1)
- [Detail Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#detail-level-log-level-2)
- [Custom Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#other-log-levels)
- [Info Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#informational-level-log-levels-6-7)
- [Debug Level Step](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#debugging-level-log-levels-8-9)
- [Block of Messages](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#printing-a-block-of-messages)
- [Message Tagging](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#printing-a-block-of-messages)

[Verifications](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verifications)
- [verify function](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verify-function-format-options-and-return)
- [Basic Usage](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#basic-usage)
- [Warnings](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#raising-warnings)
- [Failure and Warning Conditions](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verifications-including-failure-and-warning-conditions)

[aviattestlib Integration](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#integration-into-aviat-test-library-aviattestlib-modules)
- [Log Levels and Tagging](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#automatic-log-level-application-and-tagging)
- [Method Call Logging](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#method-call-logging)

[Plugin Configuration](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#plugin-configuration)
- [Verification Options](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#verification-configuration-options)

[CI Test Rig Configurations](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#ci-test-rig-configurations)
[CI Test Rig Reservations](http://nz-swbuild42:8070/slea1/pytest-phases/tree/master#ci-test-rig-reservations)

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

## Imports
Import the logging and verification APIs using:
```python
from pytest-phases import log, verify
```

## Log Messages
### Highest level (log level 1)
Print a message at the highest log level (1)
```python
log.high_level_step("Very important test step 1")
```
which is then printed in the log output as

    1-1 High level step: Very important, first test step
The first 1 is the log level and the second 1 is the step of this log level.

Note: The "High level step" printing above is just for debug use and will be removed before release.    
   
A subsequent high level message is then printed as:
    
    1-2 High level step: Second test step
where the 2 indicates it is the second step at level 1.

### Detail Level (log level 2)
Print a message at log level 2
```python
log.detail_step("More detailed test step information")
```
output:

    2-1 Detail level step: More detailed test step information
    
### Other log levels
The step function prints at the current log level if the log_level parameter is not defined
```python 
log.step("This will be the next step at the current log level")
```
output:    

    2-2 Detail level step: This will be the next step at the current log level
    
Specifying a log level using the step function:
```python
log.step("Specify the log level", log_level=3)
```
output:

    3-1 Step: Specify the log level

Increment the current log level and print the message (default increment is 1 but can be specified using the increment parameter):
```python 
log.step_increment("Increment the log level")
log.step("Another step at this incremented level")
```
output:

    4-1 Step inc: Increment the log level
    4-2 Step: Another step at this incremented level

Using the tags as detailed below will also automatically set the associated 
log level

    "HIGH": Level 0
    "DETAIL": Level 1
    "INFO": Level 6
    "DEBUG": Level 8

### Informational Level (log levels 6-7)
Print an information level message at log level 6.
```python
log.info("Informational message")
```
This is also equivalent to using the "INFO" tag in the step method.
Level 7 is used for printing blocks of messages below, see below.

### Debugging Level (log levels 8-9)
Print an information level message at log level 8.
```python    
log.debug("Informational message")
```
This is also equivalent to using the "DEBUG" tag in the step method.
Level 9 is used for printing blocks of messages below, see below.

### Printing a Block of Messages
It is possible to print a block of messages under a given message (title). 
The title is printed at the specified log level (or current level if not 
specified). In this way large blocks of related logs can easily be folded 
under the title message. 

The content defines the information to be split and printed as a
 block of messages at the next log level (log_level + 1). 
 
Content may be a:
    string (split at occurrences of '\n' and each element is printed as a 
    new message)
    list (each item is printed as a new message)
    
Example using list of strings:
```python 
log.block("Numbers 1-3", ["ONE", "TWO", "THREE"])
```
output:

    1-1 Numbers 1-3
    2-1 ONE
    2-2 TWO
    2-3 THREE

Example using newline separated string:
```python
log.block("Start of the alphabet", "A\nB\nC", log_level="INFO")
```
output:

    6-1 Start of the alphabet
    7-1 A
    7-2 B
    7-3 C

Note that after the block is printed the log level reverts to the original 
log level used by the title.

### Message Tagging
Tags can be added to messages to group or related messages or mark specific 
messages. Tags can be added as a string (comma separated) or list of strings.
Examples:
single tag
```python
log.step("Step related to a specific test rig", tags="192.11.1.2")
```
multiple tags
```python        
log.step("Step related to 2 test rigs", tags="192.11.1.1, 192.11.1.2")
```
or
```python
log.step("Step related to 2 test rigs", tags=["192.11.1.1", "192.11.1.2"])
```
    
## Verifications
### verify Function Format, Options and Return

#### Function call format
```python
verify(fail_condition, fail_message, raise_immediately=True,
       warning=False, warn_condition=None, warn_message=None,
       full_method_trace=False, stop_at_test=True, log_level=None)
```

#### Verification options:
- fail_condition:
an expression that if it evaluates to False raises a VerificationException
(or WarningException is warning is set to True).
- fail_message:
a message describing the verification being performed (requires fail_condition to be defined).
- raise_immediately (optional, default True):
whether to raise an exception immediately upon failure (same behaviour as regular assert).
- warning (optional, default None):
raise the fail_condition as a WarningException rather than VerificationException.

#### Warning options:
- warn_condition (optional, default None):
if fail_condition evaluates to True test this condition for a warning (cannot be used in addition to warning parameter).
Raises WarningException if expression evaluates to False.
- warn_message:
a message describing the warning condition being verified (requires warn_condition to be defined).

#### Traceback options:
- full_method_trace (optional, default False):
print an extended traceback with the full source of each calling function.
- stop_at_test (optional, default True):
stop printing the traceback when test function is reached (don't descend in to pytest).
- log_level (optional, default None):
the log level to assign to the verification message.
By default the verification message the log level applied is that of the previous message +1.
After printing the verification message the previous log level is restored.

#### Verification return
The verify function returns a tuple of three items:

- [0] True or False (boolean): true if verification condition (+ warning condition if applicable) passes, 
 false if condition evaluates to a warning or failure.
- [1] Status (string):
the result status of the verification, one of "PASS", "WARNING", "FAIL".
- [2] Exception type (Exception Class):
the type of exception created after evaluating the verification conditions. 
One of WarningException, VerificationException or None for a passing 
verification.


### Basic Usage
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

## Integration into Aviat Test Library (aviattestlib) Modules
### Automatic Log Level Application and Tagging
Each library has its own instance of the LibraryLogging class in its base 
class. Any tags that you wan to associate with the library are passed to the
 LibraryLogging init method. For example the VLAN library adds the tags VLAN
  and the IP address of the node it applies to:
```python
self.log = LibraryLogging([management.ip_address, "VLAN"])
```
Each message recorded by self.log.step/info/debug are then tagged 
appropriately.  
    
### Method Call Logging
Each method in the library (excluding the base class abstract methods) is 
wrapped by a special `log_method` function. Every call to the library method
 is logged at the DEBUG (8) level. The parent module and method name along 
 with its non-keyworded and keyworded arguments are logged.
 
 Example of method call logging:
 
    8-2 [45] [11.19.11.35, DEBUG, VLAN] aviattestlib.vlan.netconf.vlan_netconf_ctr8700::vlan_name, args: (100, '"Customer traffic"'), kwargs: {}
    
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

## CI Test Rig Configurations
The CI test device or rig configurations are retrieved from the test database.
Currently the test rigs are structured in a similar way to the old 
configuration file format and a test rig contains a number (1+) of devices.
This system allows a test to use the whole testrig (all devices) or a single
 device from it.
 
 To use a single device use the --device option and set it to the name of 
 the device you want to use e.g.
 
 --device=ares
 
 To use a whole test rig (all devices) you still only need to specify the 
 name of a single device but use the --testrig option instead e.g.
 
 --testrig=ares 

A file (.json) version of the configuration may be used by using the 
--config option rather than --device or --testrig. This also allows use of 
devices that do not have their configurations in the database.
 
Note that the json file versions DO NOT have the same format as the previous
 configuration files but mirror the information in the database exactly.

## CI Test Rig Reservations
The plugin checks whether the current user has reserved the specified test
device or rig before allowing a test to start. The current default behaviour
is to check the reservation if the --testrig or --device parameters are set.
To disable the reservation checking function set --no-reserve as true. The
reservation status is not checked if hte --config option is used.

## Current Limitations
- failure/warning_message parameters expect a string rather than an expression
(assert condition prints result of an expression as the exception message).

## Future Work
### Log Levels
- Add ability (via config flag) to continue to the call phase of the test if setup raises a warning (or failure)
- Choose type of exception to raise
- Add verify parameter to disable (suppress) printing and saving the result if
 it is a passes
### Verifications
Enhancement: test to decide whether teardown is required if test passes
(useful when using the same function scoped setup for multiple test functions)

Enhancement: test may inspect previous test result to check if (function) setup is required.

Possible enhancement - configuration for each setup/teardown fixture: 
- continue-to-call: continue to the test function call phase regardless of the setup result
- no-setup-if-prev-pass/warn: don't setup again (function scope) is previous test passed or warned
- teardown-on-pass: whether to teardown or not is the test passes (setup and call)
- teardown-on-warning: whether to teardown or not based on warnings (in setup and call)  
- raise-setup/call/teardown-warnings: more fine grained scope control over raising warnings
