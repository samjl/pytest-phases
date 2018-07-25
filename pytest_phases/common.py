from __future__ import print_function
##
# @file common.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18


from builtins import object
class DebugFunctionality(object):
    def __init__(self, name, enabled):
        self.name = name
        self.enabled = enabled


class ConfigOption(object):
    def __init__(self, value_type, value_default, helptext=""):
        self.value_type = value_type
        self.value = value_default
        if self.value_type is bool:
            help_for_bool = [_f for _f in [helptext, "Enable: 1/yes/true/on",
                                   "Disable: 0/no/false/off"] if _f]
            self.help = ". ".join(help_for_bool)
        else:
            self.help = helptext


DEBUG = {"print-saved": DebugFunctionality("print saved", False),
         "verify": DebugFunctionality("verify", False),
         "not-plugin": DebugFunctionality("not-plugin", False),
         "phases": DebugFunctionality("phases", False),
         "scopes": DebugFunctionality("scopes", False),
         "summary": DebugFunctionality("summary", False),
         "output-redirect": DebugFunctionality("redirect", True)}

CONFIG = {"include-verify-local-vars":
          ConfigOption(bool, True, "Include local variables in tracebacks "
                                   "created by verify function"),
          "include-all-local-vars":
          ConfigOption(bool, False, "Include local variables in all "
                                    "tracebacks. Warning: Printing all locals "
                                    "in a stack trace can easily lead to "
                                    "problems due to errored output"),
          "traceback-stops-at-test-functions":
          ConfigOption(bool, True, "Stop the traceback at the test function"),
          "raise-warnings":
          ConfigOption(bool, True, "Raise warnings (enabled) or just save the "
                                   "result (disabled)"),
          "maximum-traceback-depth":
          ConfigOption(int, 20, "Print up to the maximum limit (integer) of "
                                "stack trace entries"),
          "continue-on-setup-failure":
          ConfigOption(bool, False, "Continue to the test call phase if the "
                                    "setup fails"),
          "continue-on-setup-warning":
          ConfigOption(bool, False, "Continue to the test call phase if the "
                                    "setup warns. To raise a setup warning "
                                    "this must be set to False and "
                                    "raise-warnings set to True"),
          "no-redirect":
          ConfigOption(bool, False, "Disable output redirection"),
          "root-dir":
          ConfigOption(str, None, "Full path to local base directory to save "
                                  "test logs to"),
          "no-json":  # TODO Required now? db enable/disable
          ConfigOption(bool, False, "Don't save log to JSON file (std out "
                                    "only)")
          }


def debug_print(msg, flag):
    # Print a debug message if the corresponding flag is set.
    if flag.enabled:
        print("DEBUG({}): {}".format(flag.name, msg))
