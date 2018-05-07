# pytest-phases Plugin


# Running Tests

    pytest -s -q --tb=no -p no:logging example_tests/test_class_scope.py

The command line options can also be added to the pytest ini file for the entire project as described in the following section.

# Add pytest command line options added to ini file

Add command line options to pytest.ini (in root of testing directory):

    [pytest]
    addopts = -s -q --tb=no -p no:logging
 
* -s disable capture
* -q decrease verbosity (only effect currently is removing the "=" chars from the summary line)
* --tb=no suppress pytest tracebacks

Currently the most important issue to avoid pytest raising Attribute error and occasional freezes.
May be a conflict between this and the logging plugin but not found the root cause yet. 
Related to [this](https://github.com/pytest-dev/pytest/issues/3099) pytest defect.
* -p no:logging disable the logging plugin
