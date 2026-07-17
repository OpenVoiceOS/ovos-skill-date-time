"""End-to-end intent-routing tests for ovos-skill-date-time (en-US).

Each case feeds an utterance through a MiniCroft stack and asserts it routes
to the expected ``.intent`` handler. Coverage spans the current-time query
(bare and with a ``{location}`` slot) and the current-date/day/month/year
queries.

Run: pytest test/end2end/ -v
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LANG = "en-US"

# The intent files are padacioso samples. Exact expansions score in the -high
# band while the slotted variants land lower, so register all three bands.
PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]


class _IntentRoutingMixin:
    """Shared MiniCroft setup for padacioso intent routing."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _assert_intent(self, utterance: str, intent_file: str):
        intent_msg_type = f"{SKILL_ID}:{intent_file}"
        matched = []
        handler = lambda msg: matched.append(msg)
        self.minicroft.bus.on(intent_msg_type, handler)
        try:
            session = Session(f"e2e-en_us-{intent_file}-{hash(utterance)}")
            session.lang = LANG
            session.pipeline = PIPELINE
            message = Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            )
            # Under parallel CI load a freshly booted minicroft may not have
            # finished registering intents when the first utterance fires, so
            # re-emit until the intent routes or the deadline elapses.
            deadline = time.monotonic() + 30
            while not matched and time.monotonic() < deadline:
                self.minicroft.bus.emit(message)
                waited = time.monotonic() + 5
                while not matched and time.monotonic() < waited:
                    time.sleep(0.2)
        finally:
            self.minicroft.bus.remove(intent_msg_type, handler)
        self.assertTrue(
            matched,
            f"{utterance!r} did not route to {intent_file}",
        )


class TestQueryTime(_IntentRoutingMixin, TestCase):
    """what.time.is.it.intent"""

    def test_what_time_is_it(self):
        self._assert_intent("what time is it", "what.time.is.it.intent")

    def test_whats_the_time(self):
        self._assert_intent("what's the time now", "what.time.is.it.intent")

    def test_what_time_is_it_in_location(self):
        self._assert_intent("current time in tokyo", "what.time.is.it.intent")


class TestCurrentDate(_IntentRoutingMixin, TestCase):
    """current_date.intent"""

    def test_what_date_is_it(self):
        self._assert_intent("what date is it", "current_date.intent")

    def test_tell_me_the_date(self):
        self._assert_intent("tell me the date", "current_date.intent")


class TestCurrentDay(_IntentRoutingMixin, TestCase):
    """what.day.is.it.intent"""

    def test_what_day_is_it(self):
        self._assert_intent("what day is it", "what.day.is.it.intent")


class TestCurrentMonth(_IntentRoutingMixin, TestCase):
    """what.month.is.it.intent"""

    def test_what_month_is_it(self):
        self._assert_intent("what month is it", "what.month.is.it.intent")


class TestCurrentYear(_IntentRoutingMixin, TestCase):
    """what.year.is.it.intent"""

    def test_what_year_is_it(self):
        self._assert_intent("what year is it", "what.year.is.it.intent")
