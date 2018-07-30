##
# @file mongo.py
# @author Sam Lea (samjl) <sam.lea@avaitnet.com> <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin: mongo connector insert to and update log
# messages in mongoDB
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division
import datetime
from future import standard_library
from builtins import object, range
from pymongo import MongoClient
from .loglevels import MIN_LEVEL, MAX_LEVEL, get_parents
from .verify import SessionStatus
from .common import DEBUG
from .common import debug_print as debug_print_common
standard_library.install_aliases()

# don't bother with a timestamp - use the ObjectId
# test run (jenkins) or more generic session ID (could be an incremental
# counter in the
# database)

# DEBUG
DROP_COLLECTIONS = False


def debug_print(msg, prettify=None):
    debug_print_common(msg, DEBUG["mongo"], prettify)


def _dummy_method(*args, **kwargs):
    pass


def find_one_document(collection, match):
    try:
        doc = collection.find_one(match)
    except Exception as e:
        print("Mongo Exception Caught: {}".format(str(e)))
    else:
        debug_print("Found document:", prettify=doc)


def insert_document(collection, entry):
    try:
        res = collection.insert_one(entry)
    except Exception as e:
        print("Mongo Exception Caught: {}".format(str(e)))
    else:
        # res.acknowledged is true if write concern enabled
        debug_print("Successfully inserted document with ID {}".format(
            res.inserted_id))
        find_one_document(collection, {"_id": res.inserted_id})


def update_one_document(collection, match, update):
    try:
        # TODO add upsert option when required
        res = collection.update_one(match, update)
    except Exception as e:
        print("Mongo Exception Caught: {}".format(str(e)))
    else:
        # res.acknowledged is true if write concern enabled
        # matchedCount , modifiedCount, upsertedId
        debug_print("Successfully updated document with ID {}".format(
            res.inserted_id))
        find_one_document(collection, {"_id": res.inserted_id})


class MongoConnector(object):
    session_id = None  # FIXME move to class instance
    # hosts = None
    parents = ["-"] * (MAX_LEVEL - MIN_LEVEL)  # FIXME

    def __new__(cls, *args, **kwargs):
        if not args[0]:
            print("mongoDB disabled")
            modify_methods = []
            for attr, obj in cls.__dict__.items():
                if attr.startswith("__"):
                    continue
                if callable(obj):
                    debug_print("Modifying {}: {}".format(attr, obj))
                    modify_methods.append(attr)
            for method in modify_methods:
                setattr(cls, method, _dummy_method)
        self = super().__new__(cls)
        return self

    def __init__(self, enable, hosts):
        if enable:
            self.db = MongoClient(hosts).proto

            self.session_oid = None
            self.module_oid = None
            self.test_oid = None
            self.fix_oid = None
            self.link_oid = None

            if DROP_COLLECTIONS:
                self.db.drop_collection("sessioncounter")
                self.db.drop_collection("sessions")
                self.db.drop_collection("modules")
                self.db.drop_collection("fixtures")
                self.db.drop_collection("testresults")
                self.db.drop_collection("loglinks")
                self.db.drop_collection("testlogs")
                # self.db.drop_collection("tracebacks")

    def _get_session_id(self):
        res = self.db.sessioncounter.update_one({"_id": 0}, {"$inc": {
            "sessionId": 1}}, upsert=True)
        print(res)
        return self.db.sessioncounter.find_one({"_id": 0})["sessionId"]

    def init_session(self, collected_tests):
        # increment session counter in db and use it for the session entry
        # "session_id": session_id (unique ObjectId for the _id)
        MongoConnector.session_id = self._get_session_id()
        debug_print("Initialize test session {} in mongoDB"
                    .format(MongoConnector.session_id))
        session = dict(
            devices=[],
            testVersion=dict(
                tag=None,
                sha=None,
                branch="master"
            ),
            summaryVerify="pending",  # will be a dict
            summaryTests="pending",  # will be a dict
            plan="ObjectId link",
            sessionId=MongoConnector.session_id,
            swBuild=dict(
                branchName="",
                buildNumber=1234,
                type="ER",
                minor="",
                branchNumber="",
                major="",
                patch=""
            ),
            status="in-progress",
            progress="pending",
            expiry=False,
            collected=collected_tests,
            modules=[],
            sessionFixtures=[]
        )
        insert_document(self.db.sessions, session)


    # # DEBUG test_module for Aviat is the test ID
    # def init_module(self, test_module, run):
    #     # test run
    #     # test ID
    #
    #     # log link
    #     # overall result
    #     # verifications - list of documents
    #     # phases - phase results
    #     # fixtures applied
    #     pass

    # Every test function - created at pytest setup
    def init_test_result(self, i, test_function, test_fixtures):
        # session_status = pytest.get_session_status()
        # TODO check session_id is not None
        log_link = {
            "sessionId": MongoConnector.session_id,
            "class": SessionStatus.class_name,
            "module": SessionStatus.module,
            "testFunction": SessionStatus.test_function,
            "logIds": []
        }
        res = self.db.loglinks.insert_one(log_link)
        self.link_oid = res.inserted_id

        test_result = {
            "sessionId": MongoConnector.session_id,
            "class": SessionStatus.class_name,
            "module": SessionStatus.module,
            "testFunction": test_function,  # SessionStatus.test_function,
            # TODO add fixtures later
            "fixtures": test_fixtures,  #
            # SessionStatus.test_fixtures[SessionStatus.test_function],
            "verifications": [],
            # "setup" - update status as setup progresses and verifications
            "setup": {"logStart": i},
            # are saved
            # "call"
            # "teardown"
            "logLink": self.link_oid,
            # "result"  - single overall test result e.g. Warning,
            # Setup Failure
            "result": "pending",
            # "summary" - All saved results summary Setup: P:, F: W: could
            # be in "setup" field above
            "summary": "pending",
            "status": "in-progress",
            # Any extra test specific data can be added on as needed basis
            # e.g. dataplot data (link), protection switch times
        }
        res = self.db.testresults.insert_one(test_result)
        self.test_oid = res.inserted_id

        return res.inserted_id

        # init the loglink entry
        # TODO enhancement embed logs until document becomes large?

    def update_test_result(self, query, update):
        try:
            res = self.db.testresults.update_one(query, update)
        except Exception as e:
            print(e)
            raise
        print(res)

    # Insert the message to the testlogs collection
    # and insert the message ObjectId to the list in the corresponding
    # testloglinks item (add if required {index=1})
    # TODO timestamp in ObjectId is only to the nearest second
    def insert_log_message(self, index, level, step, message):
        # test run
        # test ID

        # SessionStatus.class_name
        # SessionStatus.module
        # SessionStatus.test_function
        # SessionStatus.test_fixtures

        # code source
        # debug

        msg = {
            "index": index,
            "level": level,
            "step": step,
            "message": escape_html(message),
            "parents": MongoConnector.parents[:level - MIN_LEVEL - 1],
            "parentIndices": get_parents(),
            "numOfChildren": 0,
            "timestamp": datetime.datetime.utcnow(),
            "testResult": self.test_oid
        }
        res = self.db.testlogs.insert_one(msg)
        # Update self.db.loglinks with the ObjectId of this message entry
        self.db.testloglinks.update_one({"_id": self.link_oid},
                                        {"$push": {"logIds": res.inserted_id}})
        # Update parent entries in the db: increment the number of children
        for parent_id in MongoConnector.parents[:level - MIN_LEVEL - 1]:
            self.db.testlogs.update_one({"_id": parent_id},
                                        {"$inc": {"numOfChildren": 1}})

        # Update the list of possible parents to include the inserted message
        # Add inserted _id for the relevant log level
        MongoConnector.parents[level - MIN_LEVEL - 1] = res.inserted_id
        # Remove possible parent at higher log levels. Required to avoid
        # incorrect number of children incrementing when log levels increment
        # by more than 1.
        for i in range(level-MIN_LEVEL, len(MongoConnector.parents)-1):
            MongoConnector.parents[i] = "-"

    # Insert a saved verification to the relevant testresults entry
    # and insert the log message and link to testlogs and testloglinks
    # respectively
    def insert_verification(self):
        # Retrieved directly from the Result object:
        # step - links back to the printed log message
        # message
        # status (FAIL, WARNING, PASS)
        # TRACKING INFO:
        # source - function, code line, local vars
        # class name
        # module
        # phase
        # test function
        # fixture name

        # debug - flags: Result.raise_immediately

        # traceback

        # TODO to add to the saved Result object
        # fail condition
        # fail message
        # warning flag?
        # warning condition (optional)
        # warning message (optional)
        pass


def escape_html(text):
    for char, replacement in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                              ('"', "&quot;"), ("'", "&#039;")):
        if char in text:
            text = text.replace(char, replacement)
    return text
