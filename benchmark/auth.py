"""Refresh benchmark clients on an actual 401, without exposing credentials to LLMs."""

import os
import threading

from agent.api_client import ApiError


def install_reauthentication(api):
    # Fake clients in offline tests need not implement the HTTP transport.
    if not hasattr(api, "_send"):
        return
    original = api._send
    lock = threading.RLock()

    def send(method, path, **kwargs):
        try:
            return original(method, path, **kwargs)
        except ApiError as error:
            if error.status_code != 401 or path.startswith("/auth/"):
                raise
            with lock:
                username, password = os.getenv("AGENT_USER"), os.getenv("AGENT_PASSWORD")
                if not username or not password:
                    raise
                api.login(username, password)
            # Only retry requests rejected by authentication, not timeouts/5xx.
            return original(method, path, **kwargs)

    api._send = send
