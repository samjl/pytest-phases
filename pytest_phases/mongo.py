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
from bson.objectid import ObjectId
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
        # find_one_document(collection, {"_id": res.inserted_id})
        return res.inserted_id


def update_one_document(collection, match, update):
    try:
        # TODO add upsert option when required
        res = collection.update_one(match, update)
    except Exception as e:
        print("Mongo Exception Caught: {}".format(str(e)))
    else:
        # res.acknowledged is true if write concern enabled
        # matchedCount , modifiedCount, upsertedId
        debug_print("Successfully matched {} and updated {} document(s)"
                    .format(res.matched_count, res.modified_count))
        # find_one_document(collection, match)


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

    def __init__(self, enable, hosts, db_name):
        if enable:
            self.db = MongoClient(hosts)[db_name]

            self.session_oid = None
            self.module_oid = None
            self.class_oid = None  # Generated embedded doc ObjectId
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
                self.db.drop_collection("verifications")
                self.db.drop_collection("tracebacks")

    def _get_session_id(self):
        res = self.db.sessioncounter.update_one({"_id": 0}, {"$inc": {
            "sessionId": 1}}, upsert=True)
        return self.db.sessioncounter.find_one({"_id": 0})["sessionId"]

    def init_session(self, collected_tests):
        """
        Insert a new test session document.
        Session document has links to all modules (and included
        classes).
        :param collected_tests: Pytest collected tests. In the format
        module::class::test
        """
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
            embeddedVersion=dict(
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
            runOrder=[],
            expiry=False,
            collected=collected_tests,
            modules=[],
            sessionFixtures=[],
            activeSetups=[]
        )
        self.session_oid = insert_document(self.db.sessions, session)

    # Insert a new module document
    # Update session document with link to new module
    # If test is in a new class then add an embedded class document to the
    # module
    def init_module(self, test_module, new_class_name):
        """
        Insert a new module document.
        Update the parent session document with ObjectId link to the
        new module.
        Insert a new embedded class to the module if required.
        :param test_module: The tests parent (new) module.
        :param new_class_name: The tests parent (new) class if it is a
        class method. If None then test is a module test only.
        """
        module = dict(
            sessionId=MongoConnector.session_id,
            classes=[],
            summaryVerify="pending",
            summaryTests="pending",
            moduleName=test_module,
            status="in-progress",
            moduleId=1,  # TODO Aviat get from test module name
            moduleFixtures=[],
            moduleTests=[]
        )
        if new_class_name:
            # Test parent is a (new) class
            # Add a new class
            module["classes"].append(
                self.create_embedded_class(new_class_name)
            )
        else:
            # Test parent is the module
            module["moduleTests"].append(self.test_oid)
        self.module_oid = insert_document(self.db.modules, module)

    def push_class_to_module(self, new_class_name):
        """
        Push a class embedded document to the parent module document.
        :param new_class_name: The name of the new class.
        """
        match = {"_id": self.module_oid}
        update = {
            "$push": {
                "classes": self.create_embedded_class(new_class_name)
            }
        }
        update_one_document(self.db.modules, match, update)

    def push_test_result_link(self, class_name):
        """
        Push the testresult ObjectId link to the parent module or class
        document.
        :param class_name: Current class name. If None the tests parent
        is a module.
        """
        if class_name:
            # Test parent is an existing class doc
            match = {
                "_id": self.module_oid,
                "classes": {"$elemMatch": {"_id": self.class_oid}}
            }
            update = {"$push": {"classes.$.classTests": self.test_oid}}
        else:
            # Test parent is an existing module doc
            match = {"_id": self.module_oid}
            update = {"$push": {"moduleTests": self.test_oid}}
        update_one_document(self.db.modules, match, update)

    def create_embedded_class(self, class_name):
        """
        Create a new embedded document.
        :param class_name: The (new) class name
        :return: class document (dict) to be inserted to relevant module
        doc
        """
        self.class_oid = ObjectId()
        class_embed = dict(
            _id=self.class_oid,
            className=class_name,
            summaryVerify="pending",
            summaryTests="pending",
            classFixtures=[],
            classTests=[self.test_oid]
        )
        return class_embed

    # TODO add log index
    def init_test_result(self, test_function, test_fixtures, new_class_name,
                         new_module_name):
        """
        Run for every test function @ pytest setup.
        Insert testresult document.
        Insert loglink document and add link to the testresult (in
        initial insert above).
        Update session document:
            update progress: "module::class::test" (fixture setup adds
            to this later),
            append to the runOrder: "module::class::test",
            add link to module (below) if required.
        Insert module document if test is in a new module.
        Insert embedded class document to module if test is in a new
        class.
        :param test_function:
        :param test_fixtures:
        :param new_class_name:
        :param new_module_name:
        :return:
        """
        if new_class_name:
            class_name = new_class_name
        else:
            class_name = SessionStatus.class_name

        if new_module_name:
            module_name = new_module_name
        else:
            module_name = SessionStatus.module

        # update session progress
        progress = "{0[0]}::{0[1]}::{0[2]}".format(SessionStatus.run_order[-1])
        match = {"_id": self.session_oid}
        update = {
            "$set": {"progress": progress},
            "$push": {"runOrder": progress}
        }
        update_one_document(self.db.sessions, match, update)

        log_link = dict(
            sessionId=MongoConnector.session_id,    # FIXME not in last ver
            className=class_name,                   # FIXME not in last ver
            moduleName=module_name,                 # FIXME not in last ver
            testName=test_function,                 # FIXME not in last ver
            logIds=[]
        )
        self.link_oid = insert_document(self.db.loglinks, log_link)

        test_result = dict(
            sessionId=MongoConnector.session_id,
            functionFixtures=[],  # links to fixture docs
            moduleName=module_name,
            className=class_name,
            testName=test_function,
            # List of Fixtures associated with the test
            fixtures=test_fixtures,
            swVersion={},
            logLink=self.link_oid,
            outcome=dict(
                setup="in-progress",
                call="pending",
                teardown="pending",
                overall="pending"
            ),
            callVerifications=[],
            callSummary={}
        )
        self.test_oid = insert_document(self.db.testresults, test_result)
        # TODO enhancement embed logs until document becomes large?

        if new_module_name:
            # Init a new module (add class to module if req), add testresult
            # link to module or class
            self.init_module(module_name, new_class_name)
        elif new_class_name:
            # Add a new class to existing module, add testresult link to class
            self.push_class_to_module(new_class_name)
        else:
            # If class: add testresult link to existing class
            # else: add testresult to existing module
            self.push_test_result_link(class_name)

    def init_fixture(self, name, scope):
        fixture = dict(
            fixtureName=name,
            setupSummary={},
            lastTest=None,
            teardownVerifications=[],
            setupVerifications=[],
            teardownSummary={},
            scope=scope,
            firstTest=None,
            setupOutcome="pending",
            teardownOutcome="pending"
        )
        self.fix_oid = insert_document(self.db.fixtures, fixture)

    def update_test_result(self, query, update):
        try:
            res = self.db.testresults.update_one(query, update)
        except Exception as e:
            print(e)
            raise
        print(res)

    def insert_log_message(self, index, level, step, message):
        """
        Insert a log mesasge to the testlogs collection. Insert the
        message ObjectId to the list in the corresponding loglinks
        document.
        Note: ObjectId is only to the nearest second so datetime
        generated time is inserted.
        :param index: The message index (running index of test module
        logs)
        :param level: The log level.
        :param step: The current log step for the assigned level.
        :param message: The log message.
        :return:
        """
        # TODO add? SessionStatus.class_name, SessionStatus.module,
        # SessionStatus.test_function, SessionStatus.test_fixtures
        msg = dict(
            index=index,
            level=level,
            step=step,
            message=escape_html(message),
            parents=MongoConnector.parents[:level - MIN_LEVEL - 1],
            parentIndices=get_parents(),
            numOfChildren=0,
            timestamp=datetime.datetime.utcnow(),
            testResult=self.test_oid
        )
        # Insert the log message
        res = self.db.testlogs.insert_one(msg)
        # Update self.db.loglinks with the ObjectId of this message entry
        self.db.loglinks.update_one({"_id": self.link_oid},
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

    def insert_verification(self, saved_result):
        """
        Insert a saved verification and add its ObjectId to the relevant
        testresult or fixture (setup or teardown) document.
        Update relevant summary entry (fixture.setupSummary.
        .teardownSummary, testresult.callSummary,
        moduleClass.summaryVerify, module.summaryVerify or
        session.summaryVerify.
        Note: Message and log link are added independently.
        :param saved_result: The saved verification (pass/warn/fail) or
        caught assertion.
        """
        if saved_result.traceback_link:
            # Traceback doc currently mirrors data in the verification
            # doc.
            # TODO increase the depth of the traceback here, reduce
            # the data in the verification or remove duplicate
            # data/collection.
            # Doesn't need the originally raised traceback (
            # saved_result.traceback_link.traceback) as it is raised
            # from the plugin rather than the original source.
            tb = []
            for level in saved_result.traceback_link.formatted_traceback:
                tb.append(dict(
                    location=level['location'],
                    code=level['code'],
                    locals=["{}:{}".format(k, v) for k, v in level['locals']
                            .items()]
                ))
            traceback = dict(
                type=saved_result.traceback_link.exc_type.__name__,
                tb=tb
            )
            verify_oid = insert_document(self.db.tracebacks, traceback)
        else:
            verify_oid = None

        verify = dict(
            level1Msg=saved_result.step,
            verifyMsg=saved_result.msg,
            status=saved_result.status,
            type=saved_result.type_code,
            source=dict(
                code=saved_result.source["code"],
                locals=["{}:{}".format(k, v) for k, v in saved_result.source[
                    "locals"].items()],
                location=saved_result.source["module-function-line"]
            ),
            fullTraceback=verify_oid,
            immediate=saved_result.raise_immediately,
            moduleName=saved_result.module,  # could use SessionStatus.module
            className=saved_result.class_name,  # SessionStatus.class_name
            testName=saved_result.test_function,  # SessionStatus.test_function
            # TODO add testLink
            fixtureName=saved_result.fixture_name,
            phase=saved_result.phase,
            scope=saved_result.scope,
            activeSetups=saved_result.active
        )
        # TODO add defect and analysis if required
        res = insert_document(self.db.verifications, verify)  # FIXME remove

        # TODO add the embedded verification document to the parent
        # tesresult or fixture (setup or teardown)

        # TODO to add to the saved Result object
        # fail condition
        # fail message
        # warning flag?
        # warning condition (optional)
        # warning message (optional)


def escape_html(text):
    for char, replacement in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                              ('"', "&quot;"), ("'", "&#039;")):
        if char in text:
            text = text.replace(char, replacement)
    return text
