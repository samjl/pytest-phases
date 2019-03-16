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
            msg_list = re.split('\r\n|\n|\r', msg)
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
                self.write_log_to_console(msg_line, log_level, step, index,
                                          tags)
                SessionStatus.mongo.insert_log_message(index, log_level, step,
                                                       msg_line, tags)
                increment_level(-1)

        else:
            log_level = get_current_level()
            tags = get_tags()
            if msg == "":
                # Printing empty message
                step, index = get_current_step(log_level)
                self.write_log_to_console(msg, log_level, step, index, tags)
                SessionStatus.mongo.insert_log_message(index, log_level, step,
                                                       msg, tags)
            else:
                # split \n and print separately for each line
                msg_list = msg.split('\n')
                msg_list = [_f for _f in msg_list if _f]
                if msg_list:
                    if len(msg_list) == 1:
                        step, index = get_current_step(log_level)
                        self.write_log_to_console(msg_list[0], log_level, step,
                                                  index, tags)
                        SessionStatus.mongo.insert_log_message(
                            index, log_level, step, msg_list[0], tags
                        )
                    # MongoDB bulk insert for single prints with string
                    # message split with \n character.
                    if len(msg_list) > 1:
                        # FIXME add a parameter for this console_suppress_block
                        if len(msg_list) > 5000:
                            self.printStdout.write(
                                "WARNING: Console log has been suppressed "
                                "because this block is longer than 5000 "
                                "lines\n"
                            )
                            self.printStdout.flush()
                            suppress = True
                        else:
                            suppress = False
                        msgs = []
                        for i, msg_line in enumerate(msg_list):
                            msg_clean = self.clean_message(msg_line)
                            if i == 0:
                                step, index = get_current_step(log_level)
                            else:
                                step, index = get_step_for_level(log_level)
                            parent_indices = list(get_parents())
                            msgs.append(dict(
                                index=index,
                                level=log_level,
                                step=step,
                                message=msg_clean,
                                tags=tags,
                                parent_indices=parent_indices
                            ))

                            if not suppress:
                                self.write_log_to_console(
                                    msg_clean, log_level, step, index, tags
                                )
                        # Bulk insert the block of messages
                        SessionStatus.mongo.bulk_insert_log_messages(msgs)

    def flush(self):
        # Do nothing. Flush is performed in write -> write_log_step ->
        # writeToStdout
        return

    def isatty(self):
        return False

    def clean_message(self, msg):
        msg = re.sub('[\r\n]', '', msg)
        msg = msg.rstrip()
        if not isinstance(msg, str):
            msg = str(msg, errors='replace')
        return msg

    def write_log_to_console(self, msg, level, step, index, tags):
        # Write the log message to the console (original stdout before
        # redirection).
        if tags:
            tags_console = " [{}]".format(", ".join(get_tags()))
        else:
            tags_console = ""

        if (CONFIG["terminal-max-level"].value is None or
                level <= CONFIG["terminal-max-level"].value):

            self.printStdout.write("{0}-{1} [{2}]{3} {4}\n".format(
                level, step, index, tags_console, msg))
            self.printStdout.flush()
