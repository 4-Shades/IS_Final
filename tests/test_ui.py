import datetime
from pathlib import Path
from unittest import mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

UI = str(Path(__file__).resolve().parent.parent / "travel_ui.py")


class _Response:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._body


def _plan(post) -> AppTest:
    with mock.patch("requests.post", post):
        app = AppTest.from_file(UI, default_timeout=30)
        app.run()
        app.text_input[0].input("Manila")
        app.text_input[1].input("Paris")
        app.date_input[1].set_value(datetime.date.today() + datetime.timedelta(days=4))
        app.button[0].click().run()
    return app


def _status(app: AppTest):
    # The status sits in the container created right under the title, above the form.
    return app.main.children[1].children[0].proto


PLAN = {"flights": [{"airline": "X"}], "stay": [{"name": "Y"}], "activities": [{"name": "Z"}]}


@pytest.mark.parametrize(
    ("body", "label", "icon"),
    [
        ({**PLAN, "errors": []}, "Trip planned in", ":material/check:"),
        (
            {**PLAN, "errors": [{"service": "stay", "message": "down"}]},
            "with some parts missing",
            ":material/error:",
        ),
    ],
)
def test_status_shows_the_outcome_at_the_top_of_the_page(body, label, icon):
    status = _status(_plan(lambda *a, **k: _Response(body)))
    assert label in status.label
    # The icon marks the outcome; older Streamlit versions have no separate state field.
    assert status.icon == icon


def test_status_reports_an_unreachable_host():
    def unreachable(*args, **kwargs):
        raise requests.ConnectionError("host unreachable")

    app = _plan(unreachable)
    assert _status(app).label == "Trip planning failed"
    assert "host unreachable" in app.error[0].value
