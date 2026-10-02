"""
Shared pytest fixtures.
"""

from __future__ import annotations

import os

import pytest
from pytest_socket import disable_socket


@pytest.fixture(autouse=True)
def setdefault_envs(request):
    if "network" not in request.node.keywords:
        os.environ.setdefault("WIKIPEDIA_BOT_USERNAME", "WIKIPEDIA_BOT_USERNAME")
        os.environ.setdefault("WIKIPEDIA_BOT_PASSWORD", "WIKIPEDIA_BOT_PASSWORD")

@pytest.fixture(autouse=True)
def stop_nets(request):
    # Check if 'network' mark is present in the current test item
    if "network" in request.node.keywords:
        from pytest_socket import enable_socket

        enable_socket()
        return
    # Otherwise, disable the socket for all other tests
    disable_socket(allow_unix_socket=True)
