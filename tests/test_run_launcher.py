import threading

import pytest

from run import _wait_for_ui


class _DummyProcess:
    def __init__(self, poll_state=None):
        self._poll_state = poll_state

    def poll(self):
        return self._poll_state


def test_wait_for_ui_exits_when_shutdown_event_is_set() -> None:
    event = threading.Event()
    event.set()

    with pytest.raises(KeyboardInterrupt):
        _wait_for_ui(_DummyProcess(), event)


def test_wait_for_ui_returns_when_process_has_exited() -> None:
    assert _wait_for_ui(_DummyProcess(poll_state=0), threading.Event()) is None
