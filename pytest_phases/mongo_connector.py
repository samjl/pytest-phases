##
# @file mongo_connector.py
# @author Sam Lea (samjl) <samjlea@gmail.com>
# @created 03/01/18
# @brief pytest phases plugin:mongo connector -

import pytest
from pymongo import MongoClient

# don't bother with a timestamp - use the ObjectId
# test run (jenkins) or more generic session ID (could be an incremental
# counter in the
# database)


class MongoConnector(object):
    session_id = None

    def __init__(self):
        self.db = MongoClient().proto
        # test ID
        # test run

        # phase
        # fixture
        # test function

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

    # DEBUG test_module for Aviat is the test ID
    def init_module(self, test_module, run):
        # test run
        # test ID

        # log link
        # overall result
        # verifications - list of documents
        # phases - phase results
        # fixtures applied
        pass

    # Every test function - created at pytest setup
    def init_test_result(self, i):
        session_status = pytest.get_session_status()
        # TODO check session_id is not None
        log_link = {
            "sessionId": MongoConnector.session_id,
            "class": session_status["class"],
            "module": session_status["module"],
            "testFunction": session_status["function"],
            "logIds": []
        }
        res = self.db.loglinks.insert_one(log_link)
        link_id = res.inserted_id

        test_result = {
            "sessionId": MongoConnector.session_id,
            "class": session_status["class"],
            "module": session_status["module"],
            "testFunction": session_status["function"],
            "fixtures": session_status["fixtures"][session_status["function"]],
            "verifications": [],
            # "setup" - update status as setup progresses and verifications
            "setup": {"logStart": i},
            # are saved
            # "call"
            # "teardown"
            "logLink": link_id
            # "result"  - single overall test result e.g. Warning,
            # Setup Failure
            # "summary" - All saved results summary Setup: P:, F: W: could
            # be in "setup" field above

            # Any extra test specific data can be added on as needed basis
            # e.g. dataplot data (link), protection switch times
        }
        res = self.db.testresults.insert_one(test_result)
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
    def insert_log_message(self):
        # test run
        # test ID

        # index
        # level
        # step
        # message

        # SessionStatus.class_name
        # SessionStatus.module
        # SessionStatus.test_function
        # SessionStatus.test_fixtures

        # code source
        # debug
        pass

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
