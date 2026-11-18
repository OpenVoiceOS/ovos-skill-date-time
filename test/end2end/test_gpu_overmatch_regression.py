"""Regression test: date-time must not steal "is there a gpu in your
system" from ovos-skill-diagnostics under the REAL default pipeline.

Root cause (pre-fix): ``locale/en-US/intents/weekday_for_date.intent``
carried two bare, unqualified samples --

    is {date} a {weekday}
    was {date} a {weekday}

-- whose only fixed tokens are "is"/"was" + "a", four tokens total. A
template engine matches structure, not entity membership; the fixed tokens
"is"/"a" (or "was"/"a") land in exactly the right positions for "is there a
gpu in your system" (is=is, {date}=there, a=a, {weekday}='gpu in your
system'), so the template matched at high-tier confidence and won the turn
away from ovos-skill-diagnostics' query_gpu intent -- even though neither
slot's filler is a real date or weekday.

The fix drops those two bare lines, keeping only the "on"-qualified /
"fall on" phrasings ("is {date} on a {weekday}", "was {date} on a
{weekday}", "does {date} fall on a {weekday}", "will {date} be on a
{weekday}"), which do not structurally collide with "is there a gpu in your
system" style utterances.

This test boots a two-skill MiniCroft (date-time + diagnostics) and asserts
date-time's weekday_for_date intent does not claim the utterance.

Run: pytest test/end2end/test_gpu_overmatch_regression.py -v --timeout=150
"""
import os
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft
from padacioso import IntentContainer

INTENT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "locale", "en-US", "intents", "weekday_for_date.intent")

DATE_TIME_SKILL_ID = "ovos-skill-date-time.openvoiceos"
DIAGNOSTICS_SKILL_ID = "ovos-skill-diagnostics.openvoiceos"
LANG = "en-US"

UTTERANCE = "is there a gpu in your system"

# date-time's own weekday_for_date intent event, the thing that used to
# fire (falsely) for this utterance.
DATE_TIME_EVENT = f"{DATE_TIME_SKILL_ID}:weekday_for_date"


class TestGpuOvermatchEngineLevel(TestCase):
    """Fast, deterministic root-cause proof at the template-engine level
    (no MiniCroft boot): a bare "is {date} a {weekday}" sample matches "is
    there a gpu in your system" token for token, so padacioso returns it
    with full confidence. With only the qualified samples, the utterance
    does not match weekday_for_date at a high-tier confidence.
    """

    def test_confidence_no_longer_near_perfect(self):
        with open(INTENT_FILE, encoding="utf-8") as f:
            samples = [line.strip() for line in f
                       if line.strip() and not line.startswith("#")]
        container = IntentContainer(fuzz=False)
        container.add_intent("weekday_for_date", samples)
        data = container.calc_intent(UTTERANCE) or {}
        conf = data.get("conf", 0.0) if data.get("name") else 0.0
        self.assertLess(
            conf, 0.8,
            f"weekday_for_date still near-perfectly matches the "
            f"GPU utterance (conf={conf}); over-general sample(s) "
            f"not fully removed")


class TestGpuOvermatchRegression(TestCase):
    """date-time must not claim a diagnostics-owned utterance."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft(
            [DATE_TIME_SKILL_ID, DIAGNOSTICS_SKILL_ID], lang=LANG, max_wait=150)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def test_date_time_does_not_claim_gpu_utterance(self):
        session = Session("e2e-gpu-overmatch-regression")
        session.lang = LANG
        session.pipeline = PIPELINE
        message = Message(
            "recognizer_loop:utterance",
            {"utterances": [UTTERANCE], "lang": LANG},
            {"session": session.serialize()},
        )
        capture = CaptureSession(self.minicroft,
                                 eof_msgs=["ovos.utterance.handled"])
        capture.capture(message, timeout=30)
        TALLY.assert_not_routed(UTTERANCE, [DATE_TIME_EVENT],
                                [m.msg_type for m in capture.finish()])
