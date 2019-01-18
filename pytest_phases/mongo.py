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
import time
from future import standard_library
from builtins import object, range
from pymongo import MongoClient
from _pytest.runner import CallInfo
from bson.objectid import ObjectId
from .loglevels import MIN_LEVEL, MAX_LEVEL, get_parents
from .verify import SessionStatus
from .common import DEBUG, CONFIG
from .common import debug_print as debug_print_common
from .outcomes import hierarchy
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
        return None
    else:
        debug_print("Found document:", prettify=doc)
        return doc


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
        # could use upsert option in future if required
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
    parents = ["-"] * (MAX_LEVEL - MIN_LEVEL + 1)

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
            self.session_id = None
            self.session_oid = None
            self.module_oid = None
            self.class_oid = None  # Generated embedded doc ObjectId
            self.test_oid = None
            self.fix_oid = []
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
        self.session_id = self._get_session_id()
        print("Initialize test session {} in mongoDB {}".format(
            self.session_id, self.db.name))

        branches = [x.strip() for x in CONFIG["test-branch"].value.split(",")]
        submodules = [x.strip() for x in CONFIG["test-submodules"].value.
                      split(",")]

        test_version = dict(
            tag=CONFIG["test-tag"].value,
            sha=CONFIG["test-sha"].value,
            branch=branches,
            submodules=submodules,
        )
        if CONFIG["jenkins-job-name"].value:
            test_version["jenkinsJobName"] = CONFIG["jenkins-job-name"].value
        if CONFIG["jenkins-job-number"].value:
            test_version["jenkinsJobNumber"] = CONFIG[
                "jenkins-job-number"].value
        if CONFIG["trigger-job-name"].value:
            test_version["triggerJobName"] = CONFIG["trigger-job-name"].value
        if CONFIG["trigger-job-number"].value:
            test_version["triggerJobNumber"] = CONFIG[
                "trigger-job-number"].value

        test_rig = CONFIG["config"].value
        if test_rig and test_rig.endswith(".json"):
            test_rig = test_rig[:-5]
        embedded_version = dict(
            branchName=CONFIG["sw-branch-name"].value if CONFIG[
                "sw-branch-name"].value else None,
            buildNumber=CONFIG["sw-build-number"].value if CONFIG[
                "sw-build-number"].value else None,
        )
        if CONFIG["release-type"].value:
            embedded_version["type"] = CONFIG["release-type"].value
        if CONFIG["sw-minor"].value:
            embedded_version["minor"] = CONFIG["sw-minor"].value
        if CONFIG["sw-branch-number"].value:
            embedded_version["branchNumber"] = CONFIG["sw-branch-number"].value
        if CONFIG["sw-major"].value:
            embedded_version["major"] = CONFIG["sw-major"].value
        if CONFIG["sw-patch"].value:
            embedded_version["patch"] = CONFIG["sw-patch"].value

        session = dict(
            testRig=test_rig,
            devices=[],  # FIXME is this still useful?
            testVersion=test_version,
            plan="ObjectId link",
            sessionId=self.session_id,
            embeddedVersion=embedded_version,
            status="in-progress",
            # pending/queued/in-progress/stalled/paused/complete
            progress=dict(
                completed=dict(),
                activeSetups=[],
                phase=None
            ),
            runOrder=[],  # List of embedded docs
            expiry=False,
            collected=collected_tests,
            modules=[],
            sessionFixtures=[],
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
            sessionId=self.session_id,
            classes=[],
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

        # Add the module ObjectID link to the parent session
        match = {"_id": self.session_oid}
        update = {"$push": {"modules": self.module_oid}}
        update_one_document(self.db.sessions, match, update)

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
                         new_module_name, setup_outcome):
        """
        Run for every test function @ pytest setup.
        Insert testresult document.
        Insert loglink document and add link to the testresult (in
        initial insert above).
        Update session document:
            update progress phase;
            append to the runOrder: module, class, test;
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

        # Update the parent session progress and runOrder (module link is
        # added later)
        run_order_oid = ObjectId()
        match = {"_id": self.session_oid}
        update = {
            "$push": {
                "runOrder": dict(
                    _id=run_order_oid,
                    moduleName=module_name,
                    className=class_name,
                    testName=test_function,
                    status="in-progress",
                    outcome=setup_outcome,
                    duration="pending"
                )
            },
            "$set": {
                "progress.phase": "setup"
             }
        }
        update_one_document(self.db.sessions, match, update)

        log_link = dict(
            sessionId=self.session_id,
            className=class_name,
            moduleName=module_name,
            testName=test_function,
            logIds=[]
        )
        self.link_oid = insert_document(self.db.loglinks, log_link)

        test_result = dict(
            sessionId=self.session_id,
            runOrderId=run_order_oid,
            functionFixtures=[],  # links to fixture docs
            moduleName=module_name,
            className=class_name,
            testName=test_function,
            # List of Fixtures associated with the test
            fixtures=test_fixtures,
            swVersion={},
            logLink=self.link_oid,
            status="in-progress",
            outcome=dict(
                # Class, module scope setups already active.
                setup=setup_outcome,
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
            setupOutcome="in-progress",
            teardownOutcome="pending"
        )
        self.fix_oid.append(insert_document(self.db.fixtures, fixture))

        # Add fixture ObjectID link to parent (session.sessionFixtures,
        # modules.moduleFixtures, modules.classes.classFixtures or
        # testresults.functionFixtures)
        if scope == "function":
            # add OId to testresult
            match = {"_id": self.test_oid}
            update = {"$push": {"functionFixtures": self.fix_oid[-1]}}
            collection = self.db.testresults
        elif scope == "class":
            # Test parent is an existing class doc
            match = {
                "_id": self.module_oid,
                "classes": {"$elemMatch": {"_id": self.class_oid}}
            }
            update = {"$push": {"classes.$.classFixtures": self.fix_oid[-1]}}
            collection = self.db.modules
        elif scope == "module":
            match = {"_id": self.module_oid}
            update = {"$push": {"moduleFixtures": self.fix_oid[-1]}}
            collection = self.db.modules
        elif scope == "session":
            match = {"_id": self.session_oid}
            update = {"$push": {"sessionFixtures": self.fix_oid[-1]}}
            collection = self.db.sessions
        else:
            raise AssertionError("Unknown fixture scope {}".format(scope))
        update_one_document(collection, match, update)

    def update_fixture_setup(self, name, outcome, summary):
        # Update session active setups and progress.completed (fixture setup)
        match = {"_id": self.session_oid}
        update = {
            "$push": {
                "progress.activeSetups": name
            },
            "$set": {
                "progress.completed": dict(
                    moduleName=SessionStatus.module,
                    className=SessionStatus.class_name,
                    # test name could be set to None for class+ scopes
                    testName=SessionStatus.test_function,
                    fixtureName=name,
                    phase="setup",
                    outcome=outcome,
                    verifications=summary
                )
            }
        }
        update_one_document(self.db.sessions, match, update)

        # Update testresult: outcome (depends upon all fixtures),
        # check fixture in expected "fixtures" list?
        # FIXME is this even required?

        # Update fixture: setupOutcome
        match = {"_id": self.fix_oid[-1]}
        update = {"$set": {"setupOutcome": outcome}}
        update_one_document(self.db.fixtures, match, update)

        # For fixture setup update the current test (first test associated
        # with this setup) outcome. Update the session runOrder outcome.
        self._update_tests_in_fixture_scope([self.test_oid], outcome, "setup")

    def _update_tests_in_fixture_scope(self, test_oids, fixture_outcome,
                                       phase, tests_complete=False):
        # TODO If progress.activeSetups
        for test_oid in test_oids:
            doc = find_one_document(self.db.testresults, {"_id": test_oid})
            debug_print("{} - {} outcome initial: {}".format(
                        doc["testName"], phase, doc["outcome"][phase]))
            # Check if the phase outcome requires updating.
            debug_print("comparing with fixture outcome: {}"
                        .format(fixture_outcome))
            phase_outcome = doc["outcome"][phase]
            initial_index = hierarchy.index(phase_outcome)
            debug_print("Initial index = {}".format(initial_index))
            if hierarchy.index(fixture_outcome) < initial_index:
                debug_print("{} outcome update required"
                            .format(phase.capitalize()))
                phase_outcome = fixture_outcome
                update_phase_outcome = True
            else:
                update_phase_outcome = False

            # Update the overall outcome, compare all phases. Note that this
            # checks the current fixture setup outcome against the current
            # cumulative setup outcome.
            debug_print("Phase outcomes:", prettify={
                "setup": doc["outcome"]["setup"],
                "call": doc["outcome"]["call"],
                phase: phase_outcome  # could overwrite setup entry above
            })
            overall_index = min(hierarchy.index(doc["outcome"]["setup"]),
                                hierarchy.index(doc["outcome"]["call"]),
                                hierarchy.index(phase_outcome))
            overall_outcome = hierarchy[overall_index]
            debug_print("Overall outcome: {} [{}]".format(overall_outcome,
                                                          overall_index))
            # Update testresult outcome
            match = dict(_id=test_oid)
            update = {"$set": {"outcome.overall": overall_outcome}}
            if update_phase_outcome:
                update["$set"]["outcome.{}".format(phase)] = phase_outcome
            # check phase just to be certain
            if phase == "teardown" and tests_complete:
                update["$set"]["status"] = "complete"

            debug_print("Updating testresult.outcome.overall (and {} if req)"
                        .format(phase))
            update_one_document(self.db.testresults, match, update)

            # Update session.runOrder (Uses _id link in associated testresult).
            run_order_oid = doc["runOrderId"]
            match = {"_id": self.session_oid,
                     "runOrder._id": run_order_oid}
            update = {"$set": {"runOrder.$.outcome": overall_outcome}}
            if phase == "teardown" and tests_complete:
                update["$set"]["runOrder.$.status"] = "complete"
            debug_print("Updating session.runOrder outcome")
            update_one_document(self.db.sessions, match, update)

    def _get_test_oids_in_fixture_scope(self, scope):
        # For module or class scoped fixtures update all corresponding test
        # outcomes and session.runOrder. Note: does not cover session scoped
        # fixtures.
        if scope == "module":
            doc = self.db.modules.find_one(
                {"_id": self.module_oid},
                # Projection
                {"_id": 0, "moduleTests": 1, "classes.classTests": 1}
            )
            test_oids = doc["moduleTests"]
            for class_doc in doc["classes"]:
                test_oids.extend(class_doc["classTests"])
            debug_print("All test oids in module:", prettify=test_oids)
        elif scope == "class":
            doc = self.db.modules.find_one(
                {"_id": self.module_oid, "classes._id": self.class_oid},
                # Projection
                {"_id": 0, "classes.$": 1}
            )
            class_doc = doc["classes"][0]
            test_oids = class_doc["classTests"]
            debug_print("All test oids in class:", prettify=test_oids)
        elif scope == "function":
            test_oids = [self.test_oid]
        return test_oids

    def update_fixture_teardown(self, name, outcome, summary, scope):
        match = {"_id": self.session_oid}
        # session progress
        update_session = {
            "$set": {
                "progress.completed": dict(
                    moduleName=SessionStatus.module,
                    className=SessionStatus.class_name,
                    # test name could be set to None for class+ scopes
                    testName=SessionStatus.test_function,
                    fixtureName=name,
                    phase="teardown",
                    outcome=outcome,
                    verifications=summary
                )
            }
        }
        # remove setup fixture from session's active setup list if present
        pipeline = [
            {"$match": {"_id": self.session_oid}},
            {"$project": {"progress.activeSetups": 1}}
        ]
        res = list(self.db.sessions.aggregate(pipeline))
        assert len(res) == 1, "Failed to get active setups for current session"
        test_complete = False
        try:
            active = res[0]['progress']['activeSetups']
        except IndexError as e:
            print("Failed to extract active setups list for current session")
        else:
            # remove the first instance of the fixture - last in, first out
            active.reverse()
            # remove first instance of fixture from reversed list
            active.remove(name)
            active.reverse()  # restore original order
            # If active length is 0 - all teardowns are complete so mark
            # test as complete.
            if not active:
                test_complete = True

        update_session["$set"].update({"progress.activeSetups": active})

        update_one_document(self.db.sessions, match, update_session)

        # Update fixture: teardownOutcome
        match = {"_id": self.fix_oid.pop()}
        update = {"$set": {"teardownOutcome": outcome}}
        update_one_document(self.db.fixtures, match, update)

        test_oids = self._get_test_oids_in_fixture_scope(scope)
        self._update_tests_in_fixture_scope(test_oids, outcome, "teardown",
                                            test_complete)

    def update_teardown_phase(self):
        # Update the parent session progress
        match = {"_id": self.session_oid}
        update = {
            "$set": {
                "progress.phase": "teardown"
             }
        }
        update_one_document(self.db.sessions, match, update)

        # Update test result
        match = {"_id": self.test_oid}
        update = {
            "$set": {
                "outcome.teardown": "in-progress"
            }
        }
        update_one_document(self.db.testresults, match, update)

        # TODO Update session.runOrder to passed is is still pending

    def update_test_phase_complete(self, completed_phase, outcome, summary):
        # Update the parent session progress
        match = {"_id": self.session_oid}
        update = {
            "$set": {
                # Workaround for mongo bug:
                # https://jira.mongodb.org/browse/SERVER-21889
                "progress.completed": dict(
                    moduleName=SessionStatus.module,
                    className=SessionStatus.class_name,
                    # test name could be set to None for class+ scopes
                    testName=SessionStatus.test_function,
                    fixtureName=None,
                    phase=completed_phase,
                    outcome=outcome,
                    verifications=summary
                )
            }
        }
        debug_print_common("Update whole structure of progress.completed ("
                           "workaround)", DEBUG["dev"])
        # For tests that have no fixtures the phase outcomes, overall
        # outcome and status (complete) need to be set here.
        update_one_document(self.db.sessions, match, update)

        # Update phase outcome
        doc = self.db.testresults.find_one({"_id": self.test_oid})
        phase_outcome = doc["outcome"][completed_phase]
        if hierarchy.index(outcome) < hierarchy.index(phase_outcome):
            phase_outcome = outcome
        # Update the overall test outcome
        overall_outcome = doc["outcome"]["overall"]
        run_order_oid = doc["runOrderId"]
        match = {"_id": self.session_oid,
                 "runOrder._id": run_order_oid}
        update = {}
        if hierarchy.index(outcome) < hierarchy.index(overall_outcome):
            overall_outcome = outcome
            if "$set" not in update.keys(): update["$set"] = dict()
            update["$set"]["runOrder.$.outcome"] = overall_outcome
            debug_print("Updating session.runOrder outcome to {}"
                        .format(overall_outcome))
        if completed_phase == "teardown" and not SessionStatus.active_setups:
            if "$set" not in update.keys(): update["$set"] = dict()
            update["$set"]["runOrder.$.status"] = "complete"
        if update:
            update_one_document(self.db.sessions, match, update)

        # Update test result
        match = {"_id": self.test_oid}
        update = {
            "$set": {
                "outcome.{}".format(completed_phase): phase_outcome,
                "outcome.overall": overall_outcome
                # TODO update callSummary?
            }
        }
        if completed_phase == "teardown" and not SessionStatus.active_setups:
            update["$set"]["status"] = "complete"
        update_one_document(self.db.testresults, match, update)

    def update_pre_call_phase(self):
        # Update the parent session progress
        match = {"_id": self.session_oid}
        update = {
            "$set": {
                "progress.phase": "call",
             }
        }
        update_one_document(self.db.sessions, match, update)

        # Update test result
        match = {"_id": self.test_oid}
        update = {
            "$set": {
                "outcome.call": "in-progress"
            }
        }
        update_one_document(self.db.testresults, match, update)

    def insert_log_message(self, index, level, step, message, tags):
        """
        Insert a log message to the testlogs collection. Insert the
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
            sessionId=self.session_id,
            moduleName=SessionStatus.module,
            className=SessionStatus.class_name,
            testName=SessionStatus.test_function,
            index=index,
            level=level,
            step=step,
            message=escape_html(message),
            parents=MongoConnector.parents[:level - MIN_LEVEL],
            parentIndices=get_parents(),
            numOfChildren=0,
            timestamp=datetime.datetime.utcnow(),  # FIXME use time.time() instead
            testResult=self.test_oid,
            tags=tags
        )
        # Insert the log message
        res = self.db.testlogs.insert_one(msg)
        # Update self.db.loglinks with the ObjectId of this message entry
        self.db.loglinks.update_one({"_id": self.link_oid},
                                    {"$push": {"logIds": res.inserted_id}})
        # Update parent entries in the db: increment the number of children
        for parent_id in MongoConnector.parents[:level - MIN_LEVEL]:
            self.db.testlogs.update_one({"_id": parent_id},
                                        {"$inc": {"numOfChildren": 1}})

        # Update the list of possible parents to include the inserted message
        # Add inserted _id for the relevant log level
        MongoConnector.parents[level - MIN_LEVEL] = res.inserted_id
        # Remove possible parent at higher log levels. Required to avoid
        # incorrect number of children incrementing when log levels increment
        # by more than 1.
        for i in range(level-MIN_LEVEL+1, len(MongoConnector.parents)):
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
                # Workaround for https://github.com/pytest-dev/pytest/pull/3560
                locals_fixed = []
                for k, v in level["locals"].items():
                    if isinstance(v, CallInfo):
                        if not hasattr(v, "result"):
                            # CallInfo type object with no results attribute
                            # FIXME create a pytest debug field
                            debug_print_common("Error: Found CallInfo with no "
                                               "result attribute (workaround)",
                                               DEBUG["dev"])
                            locals_fixed.append("{}: Error: CallInfo with no "
                                                "result attribute".format(k))
                        else:
                            locals_fixed.append("{} :{}".format(k, v))

                tb.append(dict(
                    location=level['location'],
                    code=level['code'],
                    # TODO restore when above defect is fixed
                    # locals=["{}:{}".format(k, v) for k, v in level['locals']
                    #         .items()],
                    locals=locals_fixed
                    )
                )
            traceback = dict(
                type=saved_result.traceback_link.exc_type.__name__,
                tb=tb
            )
            verify_oid = insert_document(self.db.tracebacks, traceback)
        else:
            verify_oid = None

        # Get the current unix time
        time_stamp = time.time()

        verify = dict(
            timestamp=time_stamp,  # FIXME this is not the
            # same as the timestamp saved with the log message
            level1Msg=saved_result.step,
            verifyMsg=saved_result.msg,
            indexMsg=saved_result.message_index,
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
            sessionId=self.session_id,
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

        # Update parent testresult or fixture (setup or teardown):
        # 1. add embedded verification document
        # 2. increment the verification type counter
        if (saved_result.phase in ("setup", "teardown") and
                saved_result.fixture_name and self.fix_oid):
            collection = self.db.fixtures
            doc_oid = self.fix_oid[-1]
        elif (saved_result.phase == "call" and saved_result.test_function
              and self.test_oid):
            collection = self.db.testresults
            doc_oid = self.test_oid
        else:
            raise AssertionError("Failed to insert verification result, "
                                 "invalid parameters to define parent doc",
                                 saved_result.phase,
                                 saved_result.fixture_name,
                                 self.fix_oid[-1],
                                 saved_result.test_function,
                                 self.test_oid)
        verification_oid = insert_document(self.db.verifications, verify)

        update_one_document(collection,
                            {"_id": doc_oid},
                            {"$push": {"{}Verifications".format(
                                saved_result.phase): verification_oid},
                             "$inc": {"{}Summary.{}".format(saved_result.phase,
                                saved_result.type_code): 1}
                             })

        # TODO to add to the saved Result object
        # fail condition
        # fail message
        # warning flag?
        # warning condition (optional)
        # warning message (optional)

    def update_session_complete(self):
        update_one_document(self.db.sessions, dict(_id=self.session_oid),
                            {"$set": dict(status="complete")})


def escape_html(text):
    for char, replacement in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                              ('"', "&quot;"), ("'", "&#039;")):
        if char in text:
            text = text.replace(char, replacement)
    return text
