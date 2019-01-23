##
# @file outputredirect.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin:output redirect - Adds output redirection
# functionality phases plugin.
# Issues: 1. does not support terminal markup applied by pytest,
#         2. pytest output that fills console width stretches to 2
#            lines after the addition on log level etc.
from __future__ import absolute_import
import json
import logging
import os
import re
import sys
from builtins import object, str
from collections import OrderedDict
from .common import CONFIG
from .loglevels import (
    get_current_level,
    get_current_step,
    get_step_for_level,
    increment_level,
    is_level_set,
    set_level,
    get_parents,
    set_log_parameters,
    get_tags,
    set_tags
)
from .verify import SessionStatus


def _is_start_or_end(msg):
    # Detect the start/beginning or end of pytest test section.
    search = re.search("(={6}).*(begin|start|end|passed|failed|skipped)|"
                       "(-{6}).*(begin|start).*", msg.lower())
    return True if search is not None else False


class LogRedirect(object):
    def __init__(self):
        pass

    def write(self, msg):
        msg = msg.replace("\n", "")
        if msg:
            set_log_parameters(msg, 5)

    def isatty(self):
        return False


class LogOutputRedirection(object):
    # Output redirection class. Redirects sys.stdout and stderr to write
    # method below.
    json_log = None
    # json log file paths
    root_directory = None
    session_file_path = None  # created at plugin configuration stage
    test_file_path = None  # file is created in setup phase

    def __init__(self):
        self.printStdout = sys.stdout
        self.printStderr = sys.stderr

        # Redirect any messages from the python logging module.
        # All (root) loggers.
        root = logging.getLogger()
        # Set log level to info (won't print debug level messages).
        # logging_level = logging.NOTSET
        logging_level = getattr(logging, CONFIG["python-log-level"].value)
        root.setLevel(logging_level)
        redirect = LogRedirect()
        # To write directly as for print() use self rather than redirect.
        ch = logging.StreamHandler(redirect)
        ch.setLevel(logging_level)
        # For a slightly more accurate timestamp can use the logging module,
        # add: [%(asctime)s.%(msecs)03d]
        frm = "%(name)s[%(levelname)-.5s]: %(message)s"
        ch.setFormatter(logging.Formatter(frm))
        root.addHandler(ch)

    def write(self, msg):
        if isinstance(msg, bytes):
            msg = str(msg, "utf8")
        if not is_level_set():
            msg_list = msg.split('\n')
            msg_list = [_f for _f in msg_list if _f]
            for msg_line in msg_list:
                level_reset_required = _is_start_or_end(msg)
                if level_reset_required:
                    log_level = set_level(1)
                else:
                    log_level = increment_level(1)
                step, index = get_step_for_level(log_level)
                set_tags([], log_level)
                tags = get_tags()
                self.write_log_step(msg_line, log_level, step, index, tags)
                increment_level(-1)

        else:
            log_level = get_current_level()
            step, index = get_current_step(log_level)
            tags = get_tags()
            if msg == "":
                # Printing empty message
                self.write_log_step(msg, log_level, step, index, tags)
            else:
                # split \n and print separately for each line
                msg_list = msg.split('\n')
                msg_list = [_f for _f in msg_list if _f]
                if msg_list:
                    self.write_log_step(msg_list[0], log_level, step, index,
                                        tags)
                    if len(msg_list) > 1:
                        for msg_line in msg_list[1:]:
                            # If the message has been split into multiple
                            # lines then for each line the step and index
                            # are incremented. A possible design change
                            # could be to increment the index but keep
                            # the step the same. Would also apply to if
                            # log level is not set condition above.
                            step, index = get_step_for_level(log_level)
                            self.write_log_step(msg_line, log_level, step,
                                                index, tags)

    def flush(self):
        # Do nothing. Flush is performed in write -> write_log_step ->
        # writeToStdout
        return

    def isatty(self):
        return False

    def write_log_step(self, msg, level, step, index, tags):
        # Write the log message to all enabled outputs.
        msg = re.sub('[\r\n]', '', msg)
        msg = msg.rstrip()

        if not isinstance(msg, str):
            msg = str(msg, errors='replace')

        log_entry = OrderedDict()
        log_entry["index"] = index
        log_entry["level"] = level
        log_entry["step"] = step
        log_entry["text"] = msg
        log_entry["parents"] = get_parents()
        if tags:
            tags_console = "[{}]".format(", ".join(get_tags()))
        else:
            tags_console = ""

        self.printStdout.write("{0[level]}-{0[step]} [{0[index]}] {1} {0["
                               "text]}\n".format(log_entry, tags_console))
        self.printStdout.flush()

        # Complete session json log file.
        # Ensure the file always contains valid JSON.
        if LogOutputRedirection.json_log and \
                LogOutputRedirection.session_file_path:
            if os.stat(LogOutputRedirection.session_file_path).st_size != 0:
                with open(LogOutputRedirection.session_file_path, "rb+") as f:
                    f.seek(-2, os.SEEK_END)
                    f.write(",\n")
            with open(LogOutputRedirection.session_file_path, "a") as f:
                if os.stat(LogOutputRedirection.session_file_path).st_size == 0:
                    f.write("[")
                json.dump(log_entry, f, separators=(",", ":"))
                f.write("]\n")

        # Test function specific json log file. Contains setup, call
        # and teardown.
        if LogOutputRedirection.json_log and \
                LogOutputRedirection.test_file_path:
            if os.stat(LogOutputRedirection.test_file_path).st_size != 0:
                with open(LogOutputRedirection.test_file_path, "rb+") as f:
                    f.seek(-2, os.SEEK_END)
                    f.write(",\n")
            with open(LogOutputRedirection.test_file_path, "a") as f:
                if os.stat(LogOutputRedirection.test_file_path).st_size == 0:
                    f.write("[")
                json.dump(log_entry, f, separators=(",", ":"))
                f.write("]\n")

        # Insert a log message to MongoDB
        SessionStatus.mongo.insert_log_message(index, level, step, msg, tags)
