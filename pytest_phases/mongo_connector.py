##
# @file mongo_connector.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin:mongo connector -

import datetime
import pytest
from loglevels import MIN_LEVEL, MAX_LEVEL
from pymongo import MongoClient
from verify import SessionStatus

# don't bother with a timestamp - use the ObjectId
# test run (jenkins) or more generic session ID (could be an incremental
# counter in the
# database)

# DEBUG
DROP_COLLECTIONS = True


class MongoConnector(object):
    session_id = None
    hosts = None
    parents = ["-"] * (MAX_LEVEL - MIN_LEVEL)

    def __init__(self, hosts):
        # TODO add exception/check for hosts is None
        self.db = MongoClient(hosts).proto
        # test ID
        # test run

        # phase
        # fixture
        # test function
        self.test_oid = None
        self.link_oid = None

        if DROP_COLLECTIONS:
            self.db.drop_collection("sessioncounter")
            self.db.drop_collection("sessions")
            self.db.drop_collection("testresults")
            self.db.drop_collection("loglinks")
            self.db.drop_collection("testlogs")

    def _get_session_id(self):
        res = self.db.sessioncounter.update_one({"_id": 0}, {"$inc": {
            "sessionId": 1}}, upsert=True)
        print res
        return self.db.sessioncounter.find_one({"_id": 0})["sessionId"]

    def init_session(self):
        # increment session counter in db
        # and use it for the session entry
        # "_id": session_id
        MongoConnector.session_id = self._get_session_id()
        # debug_print("Initialize session {} in mongoDB".format(session_id),
        #              "mongo")
        print("Initialize session {} in mongoDB".format(
            MongoConnector.session_id))
        session = {
            "sessionId": MongoConnector.session_id,
            "executionOrder": [],
            "status": "in-progress",
            "result": "pending"
            # TODO could also add the pytest config object
            # TODO add collected items/test names
        }
        res = self.db.sessions.insert_one(session)
        # status: "in progress/complete/failed"
        # could keep track of currently executing test module, function etc.
        pass

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
            print e
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
            "message": message,
            "parents": MongoConnector.parents[:level - MIN_LEVEL - 1],
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
