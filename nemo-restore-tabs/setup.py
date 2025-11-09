#!/usr/bin/python3

# Nemo Restore Tabs

from setuptools import setup

# Setup stage
setup(
    packages=[],
    name="nemo-restore-tabs",
    version="6.4.0",
    description="Automatically save and restore opened tabs in Nemo file manager",
    author="Linux Mint",
    author_email="root@linuxmint.com",
    url="https://github.com/linuxmint/nemo-extensions",
    license="GPL3",
    
    data_files=[
        ('/usr/share/nemo-python/extensions', ['src/nemo-restore-tabs.py']),
    ]
)