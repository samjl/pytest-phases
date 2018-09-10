##
# @file common.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18

from __future__ import print_function
from builtins import object
from pprint import pformat


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
         "phases": DebugFunctionality("phases", False),
         "scopes": DebugFunctionality("scopes", False),
         "summary": DebugFunctionality("summary", False),
         "output-redirect": DebugFunctionality("redirect", True),
         "mongo": DebugFunctionality("mongo", True),
         "dev": DebugFunctionality("dev", False)}

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
          "no-json":
          ConfigOption(bool, False, "Don't save log to JSON file (std out "
                                    "only)"),
          "python-log-level":
          ConfigOption(str, "NOTSET", "Python logging module level ("
                                      "redirected to plugin log level 5)"),
          # Aviat specific options below
          "sw-major":
          ConfigOption(str, None, "Software under test major version"),
          "sw-minor":
          ConfigOption(str, None, "Software under test minor version"),
          "sw-patch":
          ConfigOption(str, None, "Software under test patch version"),
          "sw-branch-name":
          ConfigOption(str, None, "Software under test branch name"),
          "sw-branch-number":
          ConfigOption(str, None, "Software under test branch number"),
          "sw-build-number":
          ConfigOption(str, None, "Software under test build number"),
          "release-type":
          ConfigOption(str, "nightly", "Software release type"),
          "test-sha":
          ConfigOption(str, None, "cnet2 full sha of checked-out commit"),
          "test-tag":
          ConfigOption(str, None, "cnet2 checked-out commit associated tag"),
          "test-branch":
          ConfigOption(str, None, "cnet2 checked-out commit exists on these "
                                  "branches"),
          "test-submodules":
          ConfigOption(str, None, "cnet2 checked out submodule commits"),
          }


def debug_print(msg, flag, prettify=None):
    # Print a debug message if the corresponding flag is set.
    if flag.enabled:
        print("DEBUG({}): {}".format(flag.name, msg))
        if prettify:
            print(pformat(prettify, indent=4, width=80))
