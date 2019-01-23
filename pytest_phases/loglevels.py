##
# @file loglevels.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin:loglevels - functions to assign and print a log
# level to test log messages. Log messages (including standard print function)
# are assigned a log level and associated step.
from __future__ import print_function
from __future__ import absolute_import
from builtins import object, range
from .common import CONFIG

MIN_LEVEL = 0
MAX_LEVEL = 9
INFO_LEVEL = 6
DEBUG_LEVEL = 8

TAG_TO_LEVEL = {
    "HIGH": MIN_LEVEL,
    "DETAIL": MIN_LEVEL+1,
    "INFO": INFO_LEVEL,
    "DEBUG": DEBUG_LEVEL
}


class LogCommon(object):
    @staticmethod
    def step(msg, log_level=None, tags=None):
        """Print a message at the specified or current log level.
        If optional argument log_level is not specified or None
        then the log level of the previous message is applied.
        """
        set_log_parameters(msg, log_level, tags=tags)

    @staticmethod
    def info(msg, tags=None):
        """Print an informational message at log level 6."""
        set_log_parameters(msg, log_level=6, tags=tags)

    @staticmethod
    def debug(msg, tags=None):
        """Print an debug message at log level 8."""
        set_log_parameters(msg, log_level=8, tags=tags)

    @staticmethod
    def block(title, content, log_level=None, tags=None):
        """Print a python list or string containing newline characters
        across multiple lines.
        For lists each item is printed as a new message. Strings are
        split at the newline characters and each printed as a new
        message.
        The title is printed at the log level passed in or the current
        log level if not. The log level is then incremented and the
        content block printed at this level. The original log level is
        restored after the content is printed.
        """
        set_log_parameters(title, log_level, tags=tags)
        current_level = get_current_level()
        if isinstance(content, str):
            content = content.split('\n')
        for msgLine in content:
            set_log_parameters(msgLine, current_level + 1, tags=tags)
        set_level(current_level)


class LogLevel(LogCommon):
    """Class containing logging methods used to apply a log level
    to a message.
    Note: This class should not and does not need to be instantiated.
    """
    @staticmethod
    def high_level_step(msg):
        """Print a message at the highest log level."""
        set_log_parameters(msg, log_level=MIN_LEVEL)

    @staticmethod
    def detail_step(msg):
        """Print a message at the second highest log level."""
        set_log_parameters(msg, log_level=MIN_LEVEL+1)

    @staticmethod
    def verification(msg, result_type, log_level=None, tags=None):
        """Print a message relating to the result of the execution of
        the verify function or a caught exception.
        """
        verify_tags = ['VERIFY']
        append_to_tags(verify_tags, tags)
        set_log_parameters(msg, log_level, message_type=result_type,
                           tags=verify_tags)

    @staticmethod
    def step_increment(msg, increment=1):
        """Increment the current log level and print message at the
        new level.
        """
        current_level = get_current_level()
        set_log_parameters(msg, current_level + increment)


def add_library_tag(f):
    def wrapper(*args, **kwargs):
        # Add the library specific tag
        all_tags = [i for i in args[0].tag]
        if "tags" in kwargs.keys():
            append_to_tags(all_tags, kwargs["tags"])
        kwargs["tags"] = all_tags
        # Ensure the log level is greater than those that specify test
        # steps: INFO level or higher
        if "log_level" in kwargs.keys():
            if isinstance(kwargs["log_level"], str):
                kwargs["log_level"] = TAG_TO_LEVEL[kwargs["log_level"]]
            if kwargs["log_level"] < INFO_LEVEL:
                kwargs["log_level"] = INFO_LEVEL
        return f(*args, **kwargs)
    return wrapper


class LibraryLogging(LogCommon):
    def __init__(self, library_tags):
        if isinstance(library_tags, str):
            library_tags = library_tags.split(",")
        self.tag = library_tags

    @add_library_tag
    def step(self, msg, log_level=None, tags=None):
        super().step(msg, log_level, tags)

    @add_library_tag
    def info(self, msg, tags=None):
        super().info(msg, tags)

    @add_library_tag
    def debug(self, msg, tags=None):
        super().debug(msg, tags)

    @add_library_tag
    def block(self, title, content, log_level=None, tags=None):
        super().block(title, content, log_level, tags)


# Moved from namespace
def is_level_set():
    """Return True if current message being processed has a log
            level assigned. Used to differentiate between messages
            originating from this API and those from the standard print
            functions.
            Note: This function is used by the outputredirect plugin.
"""
    return MultiLevelLogging.log_level_set


def get_current_level():
    """Return the current log level.
    Note: This function is used by the outputredirect plugin.
    """
    return MultiLevelLogging.current_level


def get_current_step(log_level):
    """Given a log level return the CURRENT step and index for
    the message being processed.
    Note: This function is used by the outputredirect plugin
    when processing messages from this API.
    """
    return MultiLevelLogging.current_step[index_from_level(
        log_level)], MultiLevelLogging.current_index


def get_step_for_level(log_level):
    """Given a log level return the NEXT step and index.
    Note: This function is used by the outputredirect plugin
    when processing standard print function messages.
    """
    return get_next_step(log_level)


def increment_level(increment=1):
    """Increment the current log level."""
    log_level = MultiLevelLogging.current_level + increment
    return set_current_level(log_level)


def set_level(log_level):
    """Set the current log level."""
    return set_current_level(log_level)


def get_current_l1_msg():
    return MultiLevelLogging.current_l1_msg


def get_current_index():
    return MultiLevelLogging.current_index


def get_parents():
    return MultiLevelLogging.parent_indices


def get_tags():
    return MultiLevelLogging.tags


def get_message_type():
    return MultiLevelLogging.message_type


def append_to_tags(original, new_tags):
    if new_tags is None:
        return original
    elif isinstance(new_tags, str):
        new_tags = new_tags.split(",")
    return original.extend(new_tags)


def set_tags(tags, log_level):
    if tags is None:
        tags = []
    elif isinstance(tags, str):
        tags = tags.split(",")
    if log_level in (TAG_TO_LEVEL["INFO"], TAG_TO_LEVEL["INFO"]+1):
        tags.append("INFO")
    elif log_level in (TAG_TO_LEVEL["DEBUG"], TAG_TO_LEVEL["DEBUG"]+1):
        tags.append("DEBUG")
    tags = [x.strip() for x in tags]  # strip each tag
    tags = list(set(tags))  # remove duplicate tags
    MultiLevelLogging.tags = tags


def set_current_level(log_level):
    if isinstance(log_level, int):
        if log_level < MIN_LEVEL:
            MultiLevelLogging.current_level = MIN_LEVEL
        elif log_level > MAX_LEVEL:
            MultiLevelLogging.current_level = MAX_LEVEL
        else:
            MultiLevelLogging.current_level = log_level
    elif log_level in TAG_TO_LEVEL.keys():
        MultiLevelLogging.current_level = TAG_TO_LEVEL[log_level]
    return MultiLevelLogging.current_level


def set_log_parameters(msg, log_level, message_type=None, tags=None):
    """Prepend the string to print with the log level and step before
    printing.
    """
    if log_level is None:
        log_level = MultiLevelLogging.current_level
    valid_log_level = set_current_level(log_level)
    if MultiLevelLogging.current_level == 1:
        MultiLevelLogging.current_l1_msg = msg
    step, index = get_next_step(valid_log_level)
    MultiLevelLogging.log_level_set = True
    MultiLevelLogging.message_type = message_type
    set_tags(tags, valid_log_level)
    if CONFIG["no-redirect"].value:
        # Don't print index as it doesn't mean much in this situation
        # (not every message is given an index)
        print("{}-{} {}".format(valid_log_level, step, msg))
    else:
        # if the output redirect enabled
        print(msg)
    MultiLevelLogging.log_level_set = False
    MultiLevelLogging.message_type = None
    set_tags(None, None)


class MultiLevelLogging(object):
    # Keep track of the current log level and the step for each log
    # level.
    current_index = 0
    current_level = 1
    current_step = [0] * (MAX_LEVEL - MIN_LEVEL + 1)
    log_level_set = False
    current_l1_msg = None
    parent_indices = [None] * (MAX_LEVEL - MIN_LEVEL + 1)
    message_type = None
    tags = []


def get_next_step(log_level):
    # Return the next step and index for the specified log level.
    MultiLevelLogging.current_step[index_from_level(log_level)] += 1
    step = MultiLevelLogging.current_step[index_from_level(log_level)]
    reset_higher_levels(log_level)
    MultiLevelLogging.current_level = log_level
    MultiLevelLogging.current_index += 1
    i = index_from_level(log_level)
    MultiLevelLogging.parent_indices[i] = MultiLevelLogging.current_index
    for index in range(i+1, len(MultiLevelLogging.parent_indices)):
        MultiLevelLogging.parent_indices[index] = None
    return step, MultiLevelLogging.current_index


def index_from_level(log_level):
    # Return the current_step list index for the log level specified.
    return log_level - MIN_LEVEL


def reset_level_step(log_level):
    # Reset the step for a log level to 0. Next time this level is
    # logged the step will be set to 1.
    MultiLevelLogging.current_step[index_from_level(log_level)] = 0


def reset_higher_levels(log_level):
    # Reset step to 0 for all log levels higher than specified.
    for level in range(log_level+1, MAX_LEVEL+1):
        reset_level_step(level)
