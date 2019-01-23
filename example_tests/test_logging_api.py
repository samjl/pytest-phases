from pytest_phases import LibraryLogging, log, verify


def test_logging_api():
    log.high_level_step("High level step 1")
    log.detail_step("Detail level step 1")

    # Step method with log level set using keyword tags (applies level
    # based on tag)
    log.step("High level STEP", log_level="HIGH")
    log.step("Detail level STEP", log_level="DETAIL")
    log.step("Info", log_level="INFO")

    verify(True, "Passed verification")
    verify(False, "Failed verification as warning", warning=True)
    verify(False, "Failed verification don't raise", raise_immediately=False)

    # Library logging prototype
    lib = LibraryStub("node_0")
    lib.library_logging()
    # No library tags on these next 2 messages
    log.step("Back in test function")
    print("Still in test function")
    lib.library_log_info()


class LibraryStub(object):
    def __init__(self, device_id):
        tags = [device_id, "library_name"]
        self.log = LibraryLogging(tags)

    def library_logging(self):
        self.log.step("This is a lib message 1")
        self.log.step("This is a lib message 2", tags="TEST_TAG1")
        self.log.step("This is a lib message 3", tags=["TEST_TAG2",
                                                       "TEST_TAG3"])

        self.log.block("Library block", ["line 1", "line 2", "line 3"])
        self.log.block("Info Library block", ["line 1", "line 2", "line 3"],
                       log_level="INFO")

    def library_log_info(self):
        self.log.info("Information")
        self.log.debug("Debugging")

        self.log.step("Library level 0!", log_level=0)
        self.log.step("Library level HIGH!", log_level="HIGH")
        self.log.step("Library level 5!", log_level=5)
