"""Serving the reference agents over real HTTP, on an ephemeral port.

Used by both the test suite and the calibration script, so the gate and the tests
reach the agents the same way. The known cost of the seam choice, accepted in the
spec: calibration needs a server fixture and runs slower than an in-process
equivalent.
"""

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI

STARTUP_TIMEOUT = 10.0


@contextmanager
def serve(app: FastAPI, host: str = "127.0.0.1") -> Iterator[str]:
    """Serve an app in a background thread and yield its base URL."""
    config = uvicorn.Config(app, host=host, port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + STARTUP_TIMEOUT
    while not server.started:
        if time.monotonic() > deadline:
            server.should_exit = True
            raise TimeoutError("reference agent server did not start")
        time.sleep(0.02)

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=STARTUP_TIMEOUT)
