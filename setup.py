#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="pytest-phases",
    version='0.11.0',
    author='Sam Lea',
    author_email='samjlea@gmail.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=["pytest>=3.7.2", "future", "decorator",
                      "pymongo>=3.7.1"],
    # the following makes a plugin available to pytest
    entry_points={'pytest11': ['phases = pytest_phases.pytest_phases']},
    # custom PyPI classifier for pytest plugins
    classifiers=["Framework :: Pytest"],
)
