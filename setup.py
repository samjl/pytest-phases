#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="pytest-phases",
    version='0.2.3',
    author='Sam Lea',
    author_email='samjlea@gmail.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=["pytest>=3.0.0", "future", "decorator", "pymongo"],
    # the following makes a plugin available to pytest
    entry_points={'pytest11': ['phases = pytest_phases.pytest_phases']},
    # custom PyPI classifier for pytest plugins
    classifiers=["Framework :: Pytest"],
)
